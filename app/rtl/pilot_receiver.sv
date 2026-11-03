// Receiver sees ONLY received I/Q and public pilot/data framing.
// 32 constant +1 pilots estimate a complex direction; no atan or division
// is needed for BPSK sign(dot(sample, estimated_direction)).
module pilot_receiver(
 input wire clk,rst_n,clear,valid,pilot,first_pilot,
 input wire signed [31:0] sample_i,sample_q,
 output wire decision,
 output reg signed [37:0] estimate_i,estimate_q
);
 wire signed [69:0] pi=$signed(sample_i)*$signed(estimate_i);
 wire signed [69:0] pq=$signed(sample_q)*$signed(estimate_q);
 wire signed [70:0] dot=$signed({pi[69],pi})+$signed({pq[69],pq});
 assign decision=dot<0;
 always @(posedge clk) begin
  if(!rst_n) begin estimate_i<=0;estimate_q<=0;end
  else if(clear) begin estimate_i<=0;estimate_q<=0;end
  else if(valid&&pilot) begin
   if(first_pilot) begin estimate_i<=sample_i;estimate_q<=sample_q;end
   else begin estimate_i<=estimate_i+sample_i;estimate_q<=estimate_q+sample_q;end
  end
 end
endmodule
