// Exactly B-v1 32-byte header + 64-byte padded payload + CRC16, no FEC yet.
module payload_tx(
 input wire clk,rst_n,start,corrupt_crc,ack_frame,
 output wire [6:0] read_index,input wire [7:0] read_byte,
 output wire valid,data_bit,sop,eop,input wire ready,
 output reg busy,done,output reg [31:0] bits_sent
);
 `include "crc16_function.vh"
 reg [9:0] bit_index;reg [15:0] crc;reg corrupt;
 wire [9:0] body_bits=ack_frame?10'd96:10'd768;
 assign read_index=bit_index<body_bits?bit_index[9:3]:0;
 assign valid=busy;assign sop=busy&&bit_index==0;assign eop=busy&&bit_index==body_bits+15;
 wire plain_bit=(bit_index<body_bits)?read_byte[7-bit_index[2:0]]:crc[15-(bit_index-body_bits)];
 assign data_bit=plain_bit ^ (corrupt&&bit_index==body_bits+15);
 always @(posedge clk) begin
  if(!rst_n) begin busy<=0;done<=0;bit_index<=0;crc<=16'hffff;corrupt<=0;bits_sent<=0;end
  else if(start) begin busy<=1;done<=0;bit_index<=0;crc<=16'hffff;corrupt<=corrupt_crc;bits_sent<=0;end
  else if(valid&&ready) begin
   bits_sent<=bits_sent+1;
   if(bit_index<body_bits)crc<=crc16_step(crc,data_bit);
   if(eop)begin busy<=0;done<=1;end else bit_index<=bit_index+1;
  end
 end
endmodule
