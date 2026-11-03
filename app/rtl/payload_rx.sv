// RX buffer writes are derived only from demodulated receive bits.
// SOP/EOP remain legacy sideband framing in this interface-validation stage.
module payload_rx(
 input wire clk,rst_n,clear,valid,data_bit,sop,eop,accept_enable,ack_frame,
 output wire ready,write_enable,output wire [6:0] write_index,output wire [7:0] write_byte,
 output reg done,crc_ok,format_ok,output reg [15:0] payload_length,
 output reg [15:0] calculated_crc,received_crc,output reg [31:0] bits_received
);
 `include "crc16_function.vh"
 reg active;reg [9:0] count;reg [7:0] shift,version_byte;
 reg [15:0] crc,crc_shift,declared_len;
 wire [9:0] position=sop?10'd0:count;
 wire take=valid&&ready&&(sop||active);
 assign ready=accept_enable&&!clear;
 wire [9:0] body_bits=ack_frame?10'd96:10'd768;
 assign write_enable=take&&position<body_bits&&position[2:0]==7;
 assign write_index=position[9:3];assign write_byte={shift[6:0],data_bit};
 always @(posedge clk)begin
  if(!rst_n)begin active<=0;count<=0;shift<=0;version_byte<=0;crc<=16'hffff;crc_shift<=0;declared_len<=0;done<=0;crc_ok<=0;format_ok<=0;payload_length<=0;calculated_crc<=0;received_crc<=0;bits_received<=0;end
  else if(clear)begin active<=0;count<=0;shift<=0;version_byte<=0;crc<=16'hffff;crc_shift<=0;declared_len<=0;done<=0;crc_ok<=0;format_ok<=0;payload_length<=0;calculated_crc<=0;received_crc<=0;bits_received<=0;end
  else begin
   done<=0;
   if(take)begin
    bits_received<=bits_received+1;active<=!eop;
    count<=position==1023?10'd1023:position+1;
    shift<={shift[6:0],data_bit};
    if(sop)begin crc_shift<=0;declared_len<=0;version_byte<=0;end
    if(position<body_bits)crc<=crc16_step(sop?16'hffff:crc,data_bit);
    else if(position<body_bits+16)crc_shift<={crc_shift[14:0],data_bit};
    if(position==7)version_byte<=write_byte;
    if(position==231)declared_len[7:0]<=write_byte;
    if(position==239)declared_len[15:8]<=write_byte;
    if(eop)begin
     done<=1;crc_ok<=position==body_bits+15&&{crc_shift[14:0],data_bit}==crc;
     format_ok<=position==body_bits+15&&(ack_frame||(version_byte==1&&declared_len>=1&&declared_len<=64));
     payload_length<=ack_frame?16'd12:declared_len;calculated_crc<=crc;received_crc<={crc_shift[14:0],data_bit};
    end
   end
  end
 end
endmodule
