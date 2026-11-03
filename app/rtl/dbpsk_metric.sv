// Replaceable, combinational DBPSK decision metric. Positive means bit 0.
// The caller owns valid/ready and holds these inputs until its decision cycle.
// No transmit reference or channel configuration is available to this module.
module dbpsk_metric(
 input wire hard_profile,
 input wire signed [15:0] i,q,previous_i,previous_q,
 output wire signed [7:0] metric
);
 (* use_dsp="no",keep="true" *) wire signed [63:0] dot=
   $signed(i)*$signed(previous_i)+$signed(q)*$signed(previous_q);
 wire signed [63:0] scaled=dot>>>20;
 wire signed [7:0] soft_value=scaled>127?8'sd127:scaled< -127?-8'sd127:scaled[7:0];
 // Working alternative: discard amplitude confidence, retain differential sign.
 // Exactly zero remains an erasure rather than inventing evidence for bit 0.
 assign metric=hard_profile?(dot==0?8'sd0:dot<0?-8'sd64:8'sd64):soft_value;
endmodule
