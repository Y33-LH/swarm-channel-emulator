// Independent receiver. NO input carries TX SOP/EOP, payload, phase or delay.
// Four-sample rectangular matched filter, then four-phase PN search.
// Compare the next four candidate phases before committing to a frame origin.
// Repeat/training/SFD validation follows; acquisition is never declared by energy alone.
// Acquisition is confirmed by the second PN, training and SFD before payload.
module dbpsk_capture(
 input wire clk,rst_n,clear,in_valid,ack_frame,
 input wire signed [15:0] in_i,in_q,
 output wire in_ready,
 output reg valid,data_bit,sop,eop,input wire ready,
 output reg [31:0] captures,search_samples,sync_errors,
 output reg acquired,output reg[31:0] frame_origin,
 output reg signed [31:0] training_i,training_q,
 output reg [63:0] training_energy,
 output reg [31:0] training_count
);
 `include "pn_diff.vh"
 `include "preamble_constant.vh"
 reg [125:0] history[0:3];
 reg signed [15:0] prev_i[0:3],prev_q[0:3];
 reg signed [15:0] delay_i[0:2],delay_q[0:2];
 wire signed [17:0] sum_i=$signed({{2{in_i[15]}},in_i})+$signed({{2{delay_i[0][15]}},delay_i[0]})+$signed({{2{delay_i[1][15]}},delay_i[1]})+$signed({{2{delay_i[2][15]}},delay_i[2]});
 wire signed [17:0] sum_q=$signed({{2{in_q[15]}},in_q})+$signed({{2{delay_q[0][15]}},delay_q[0]})+$signed({{2{delay_q[1][15]}},delay_q[1]})+$signed({{2{delay_q[2][15]}},delay_q[2]});
 wire signed [15:0] matched_i=sum_i>>>2,matched_q=sum_q>>>2;
 reg [39:0] phase_power[0:3],power3,best_power;
 reg [31:0] best_index;reg[1:0] best_phase,choose_left;reg choosing;
 reg [1:0] phase,locked_phase;reg [9:0] expected_index,data_index;
 reg [9:0] pre_errors;reg [5:0] sfd_errors;reg previous_known;reg [1:0] state;
 reg center_wait;
 // Keep the signed sum in fabric. Vivado 2018.3 otherwise maps the sign
 // qualification into DSP PATTERNDETECT with CREG=1 and CLK=0; post-synthesis
 // simulation exposed a wrong constant reference despite passing RTL simulation.
 reg v1,v2,v3;reg[1:0]phase3;reg[31:0]index3;reg signed[15:0]i3,q3;reg[32:0]energy3;reg signed[32:0]dot3;reg[1:0] phase1,phase2;reg[31:0] index1,index2;
 reg signed[15:0] i1,q1,i2,q2;
 reg signed[31:0] product_i,product_q;reg signed[32:0] dot;
 reg[31:0] ei1,eq1;reg[32:0] energy2;
 wire differential_bit=dot3[32];
 always @(posedge clk)begin
  if(!rst_n)begin v1<=0;v2<=0;v3<=0;phase<=0;search_samples<=0;product_i<=0;product_q<=0;dot<=0;phase1<=0;phase2<=0;index1<=0;index2<=0;i1<=0;q1<=0;i2<=0;q2<=0;ei1<=0;eq1<=0;energy2<=0;
   for(integer p=0;p<4;p=p+1)begin prev_i[p]<=0;prev_q[p]<=0;phase_power[p]<=0;end
   for(integer p=0;p<3;p=p+1)begin delay_i[p]<=0;delay_q[p]<=0;end
  end else if(clear)begin v1<=0;v2<=0;v3<=0;phase<=0;search_samples<=0;
   for(integer p=0;p<4;p=p+1)begin prev_i[p]<=0;prev_q[p]<=0;phase_power[p]<=0;end
   for(integer p=0;p<3;p=p+1)begin delay_i[p]<=0;delay_q[p]<=0;end
  end else begin
   v1<=in_valid&&in_ready;v2<=v1;v3<=v2;
   if(v2)begin i3<=i2;q3<=q2;phase3<=phase2;index3<=index2;energy3<=energy2;dot3<=dot;
    phase_power[phase2]<=phase_power[phase2]-(phase_power[phase2]>>5)+energy2;
    power3<=phase_power[phase2]-(phase_power[phase2]>>5)+energy2;
   end
   if(in_valid&&in_ready)begin
    product_i<=$signed(matched_i)*$signed(prev_i[phase]);product_q<=$signed(matched_q)*$signed(prev_q[phase]);
    ei1<=$signed(matched_i)*$signed(matched_i);eq1<=$signed(matched_q)*$signed(matched_q);
    i1<=matched_i;q1<=matched_q;phase1<=phase;index1<=search_samples;
    prev_i[phase]<=matched_i;prev_q[phase]<=matched_q;phase<=phase+1;search_samples<=search_samples+1;
    delay_i[0]<=in_i;delay_q[0]<=in_q;
    for(integer p=1;p<3;p=p+1)begin delay_i[p]<=delay_i[p-1];delay_q[p]<=delay_q[p-1];end
   end
   if(v1)begin dot<=$signed({product_i[31],product_i})+$signed({product_q[31],product_q});energy2<={1'b0,ei1}+{1'b0,eq1};i2<=i1;q2<=q1;phase2<=phase1;index2<=index1;end
  end
 end
 wire [125:0] candidate={history[phase2][124:0],dot[32]};
 wire [127:0] mismatch={2'b0,candidate^PN_DIFF};integer k;
 wire [3:0] count8[0:15];reg[3:0]count8_reg[0:15];wire [4:0] count16[0:7];wire[5:0] count32[0:3];wire[6:0] count64[0:1];
 function automatic [3:0] pop8(input [7:0] x);reg[1:0]a,b,c,d;begin a={1'b0,x[0]}+x[1];b={1'b0,x[2]}+x[3];c={1'b0,x[4]}+x[5];d={1'b0,x[6]}+x[7];pop8=({2'b0,a}+b)+({2'b0,c}+d);end endfunction
 genvar g;
 generate
  for(g=0;g<16;g=g+1)begin:pc8 assign count8[g]=pop8(mismatch[g*8+:8]);end
  for(g=0;g<8;g=g+1)begin:pc16 assign count16[g]={1'b0,count8_reg[2*g]}+count8_reg[2*g+1];end
  for(g=0;g<4;g=g+1)begin:pc32 assign count32[g]={1'b0,count16[2*g]}+count16[2*g+1];end
  for(g=0;g<2;g=g+1)begin:pc64 assign count64[g]={1'b0,count32[2*g]}+count32[2*g+1];end
 endgenerate
 wire [7:0] errors={1'b0,count64[0]}+count64[1];
 wire candidate_good=index3>=507&&errors<=16&&dot3!=0;
 wire better_candidate=candidate_good&&power3>best_power;
 wire[31:0] selected_index=better_candidate?index3:best_index;
 wire[1:0] selected_phase=better_candidate?phase3:best_phase;
 assign in_ready=!valid||ready;
 always @(posedge clk)if(v2)for(integer pc=0;pc<16;pc=pc+1)count8_reg[pc]<=count8[pc];
 always @(posedge clk)begin
  if(!rst_n)begin
   for(k=0;k<4;k=k+1)begin history[k]<=0;end
   locked_phase<=0;expected_index<=0;data_index<=0;pre_errors<=0;sfd_errors<=0;previous_known<=0;state<=0;center_wait<=0;
   valid<=0;data_bit<=0;sop<=0;eop<=0;captures<=0;sync_errors<=0;acquired<=0;frame_origin<=0;
   training_i<=0;training_q<=0;training_energy<=0;training_count<=0;
   choosing<=0;choose_left<=0;best_power<=0;best_index<=0;best_phase<=0;
  end else if(clear)begin
   for(k=0;k<4;k=k+1)begin history[k]<=0;end
   locked_phase<=0;expected_index<=0;data_index<=0;pre_errors<=0;sfd_errors<=0;previous_known<=0;state<=0;center_wait<=0;
   valid<=0;data_bit<=0;sop<=0;eop<=0;captures<=0;sync_errors<=0;acquired<=0;frame_origin<=0;
   training_i<=0;training_q<=0;training_energy<=0;training_count<=0;
   choosing<=0;choose_left<=0;best_power<=0;best_index<=0;best_phase<=0;
  end else begin
   if(valid&&ready)valid<=0;
   if(v2)history[phase2]<=candidate;
   if(v3)begin
    if(state==0)begin
     if(!choosing&&candidate_good)begin
      choosing<=1;choose_left<=3;best_power<=power3;best_index<=index3;best_phase<=phase3;
     end else if(choosing)begin
      if(better_candidate)begin best_power<=power3;best_index<=index3;best_phase<=phase3;end
      if(choose_left==1)begin
       choosing<=0;state<=1;locked_phase<=selected_phase;center_wait<=0;
       expected_index<=127;previous_known<=preamble[126];pre_errors<=0;sfd_errors<=0;frame_origin<=selected_index-507;
       training_i<=0;training_q<=0;training_energy<=0;training_count<=0;
      end else choose_left<=choose_left-1;
     end
    end else if(phase3==locked_phase)begin
     if(center_wait)center_wait<=0;
     else if(state==1)begin
      if(expected_index>=254&&expected_index<=508)begin
       training_count<=training_count+1;
       training_i<=training_i+(preamble[expected_index]?-$signed({i3[15],i3}):$signed({i3[15],i3}));
       training_q<=training_q+(preamble[expected_index]?-$signed({q3[15],q3}):$signed({q3[15],q3}));
       training_energy<=training_energy+{31'b0,energy3};
      end
      previous_known<=preamble[expected_index];
      if(differential_bit!=(preamble[expected_index]^previous_known))pre_errors<=pre_errors+1;
      if(expected_index>=509&&expected_index<=540&&differential_bit!=(preamble[expected_index]^previous_known))sfd_errors<=sfd_errors+1;
      if(expected_index==541)begin
       if(pre_errors<=64&&({1'b0,sfd_errors}+{6'b0,(differential_bit!=(preamble[541]^previous_known))})<=4)begin state<=2;data_index<=0;captures<=captures+1;acquired<=1;end
       else begin state<=0;sync_errors<=sync_errors+1;end
      end else expected_index<=expected_index+1;
     end else if(state==2)begin
      valid<=1;data_bit<=differential_bit;sop<=data_index==0;eop<=data_index==(ack_frame?111:783);
      if(data_index==(ack_frame?111:783))state<=3;else data_index<=data_index+1;
     end
    end
   end
  end
 end
endmodule
