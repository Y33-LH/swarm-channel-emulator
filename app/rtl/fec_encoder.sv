// Exact B-v1 concatenation: PN9 scrambler, 8-row transpose, K7 (171,133),
// two terminated RSC constituents, systematic rate 1/3 Turbo serialization.
// The frame type is configuration, never receiver side-channel payload data.
module fec_encoder(
 input wire clk,rst_n,clear,ack_frame,fec_enable,
 input wire in_valid,in_bit,output wire in_ready,
 output wire out_valid,out_bit,input wire out_ready,
 output reg prepared,output wire [12:0] coded_length,
 input wire [12:0] monitor_addr,output wire monitor_bit
);
 reg bits[0:783];reg[1:0]convpairs[0:789];reg coded[0:4751];
 reg [10:0] pi_data[0:1579];reg [10:0] pi_ack[0:235];
 initial begin $readmemh("turbo_data.mem",pi_data);$readmemh("turbo_ack.mem",pi_ack);end
 reg [3:0] state;reg[12:0] k,rd;reg[8:0] scr;reg[5:0] cs;reg[2:0] r1,r2;reg[1:0]sub;
 wire[10:0] length=ack_frame?112:784;
 wire[10:0] n=ack_frame?236:1580;
 assign coded_length=fec_enable?(ack_frame?13'd720:13'd4752):{2'b0,length};
 wire[10:0] ext=(k%8)*(length/8)+(k/8);
 wire[10:0] pi=ack_frame?pi_ack[k]:pi_data[k];
 wire u=(k<length)?bits[ext]:1'b0;
 wire[6:0] q={u,cs};
 wire ck=convpairs[k[10:1]][k[0]],cp=convpairs[pi[10:1]][pi[0]];
 wire v1=ck^r1[1]^r1[0],v2=cp^r2[1]^r2[0];
 wire coded_we=(state==0&&in_valid&&in_ready)||state==2||state==3;
 wire[12:0]coded_addr=state==0?k:state==2?3*k+sub:3*n+k;
 wire tail_bit=k<6?(k[0]?(r1[2]^r1[0]):(r1[1]^r1[0])):(k[0]?(r2[2]^r2[0]):(r2[1]^r2[0]));
 wire coded_value=state==0?in_bit:state==3?tail_bit:sub==0?ck:sub==1?(v1^r1[2]^r1[0]):(v2^r2[2]^r2[0]);
 assign in_ready=state==0;
 assign out_valid=prepared&&rd<coded_length;
 assign out_bit=coded[rd];
 assign monitor_bit=coded[monitor_addr];
 always @(posedge clk)begin
  if(in_valid&&in_ready)bits[k]<=in_bit^scr[0];
  if(state==1)convpairs[k[9:0]]<={^(q&7'o133),^(q&7'o171)};
  if(coded_we)coded[coded_addr]<=coded_value;
 end
 always @(posedge clk)begin
  if(!rst_n)begin state<=0;k<=0;rd<=0;scr<=511;cs<=0;r1<=0;r2<=0;prepared<=0;sub<=0;end
  else if(clear)begin state<=0;k<=0;rd<=0;scr<=511;cs<=0;r1<=0;r2<=0;prepared<=0;sub<=0;end
  else begin
   if(in_valid&&in_ready)begin
    scr<={(scr[0]^scr[5]),scr[8:1]};
    if(k==length-1)begin k<=0;state<=fec_enable?1:4;if(!fec_enable)prepared<=1;end else k<=k+1;
   end
   if(state==1)begin cs<=q[6:1];if(k==length+5)begin k<=0;state<=2;end else k<=k+1;end
   if(state==2)begin if(sub==2)begin sub<=0;r1<={v1,r1[2:1]};r2<={v2,r2[2:1]};if(k==n-1)begin k<=0;state<=3;end else k<=k+1;end else sub<=sub+1;end
   if(state==3)begin if(k[0])begin if(k<6)r1<={1'b0,r1[2:1]};else r2<={1'b0,r2[2:1]};end if(k==11)begin prepared<=1;state<=4;end else k<=k+1;end
   if(out_valid&&out_ready)rd<=rd+1;
  end
 end
endmodule
