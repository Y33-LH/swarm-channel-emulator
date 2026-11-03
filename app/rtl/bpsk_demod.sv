// Ideal phase/timing synchronization. A zero sample decides bit 0.
module bpsk_demod(input wire signed [31:0] sample, output wire data_bit);
 assign data_bit = sample[31];
endmodule
