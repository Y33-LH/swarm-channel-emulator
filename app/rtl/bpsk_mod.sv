// One real sample/symbol at an ideal matched-filter decision instant.
// 0 -> +8192, 1 -> -8192. Q path is identically zero.
module bpsk_mod(input wire data_bit, output wire signed [15:0] sample);
 assign sample = data_bit ? -16'sd8192 : 16'sd8192;
endmodule
