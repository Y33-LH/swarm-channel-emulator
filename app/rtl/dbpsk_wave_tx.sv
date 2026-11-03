// Stage-2 acquisition baseline: rectangular 4 samples/symbol, Q14 amplitude .5.
// B-v1 preamble; DBPSK raw body. RRC/FEC are later, explicitly separate gates.
module dbpsk_wave_tx(
 input wire clk,rst_n,clear,advance,suppress,ack_frame,fec_enable,
 input wire [10:0] start_delay,
 input wire payload_valid,payload_bit,
 output wire payload_ready,
 output wire signed [15:0] sample_i,
 output wire [31:0] sample_count
);
 `include "preamble_constant.vh"
 reg [31:0] count; reg [12:0] symbol_index;reg [1:0] sub_sample;
 reg differential_sign;
 wire[12:0] body=fec_enable?(ack_frame?720:4752):(ack_frame?112:784);
 wire active=count>=128+start_delay && symbol_index<542+body;
 wire negative=(symbol_index<542)?preamble[symbol_index]:((sub_sample==0)?(differential_sign^payload_bit):differential_sign);
 assign sample_i=(!suppress&&active&&(symbol_index<542||sub_sample!=0||payload_valid))?(negative?-16'sd8192:16'sd8192):16'sd0;
 assign payload_ready=advance&&active&&symbol_index>=542&&sub_sample==0;
 assign sample_count=count;
 always @(posedge clk)begin
  if(!rst_n)begin count<=0;symbol_index<=0;sub_sample<=0;differential_sign<=0;end
  else if(clear)begin count<=0;symbol_index<=0;sub_sample<=0;differential_sign<=0;end
  else if(advance)begin
   count<=count+1;
   if(active)begin
    sub_sample<=sub_sample+1;
    if(symbol_index>=542&&sub_sample==0)differential_sign<=negative;
    if(sub_sample==3)begin
     symbol_index<=symbol_index+1;
    end
   end
  end
 end
endmodule
