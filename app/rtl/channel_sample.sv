// Reproducible quantized Gaussian approximation, NOT a certified AWGN source.
// 4096 inverse-normal midpoint quantiles, Q12; tails limited to +/-3.668 sigma.
// Gain is unsigned Q1.15 (0..32768), sigma in ADC-like amplitude units.
// No external ADC required. All arithmetic stays digital.
module channel_sample (
 input wire clk, rst_n, clear, link_enable,
 input wire [15:0] threshold, seed, gain_q15,
 input wire signed [15:0] echo_q14,
 input wire [4:0] delay_symbols,
 input wire [31:0] phase_initial,phase_step,
 input wire [31:0] echo_initial,echo_step,fade_step0,fade_step1,
 input wire [15:0] fade_depth0,fade_depth1,
 input wire [1:0] ideal_compensation,
 input wire in_valid, in_bit, in_sop, in_eop,
 output wire in_ready,
 output reg out_valid, out_bit, out_sop, out_eop,
 input wire out_ready,
 output wire [15:0] lfsr_state,
 output reg [31:0] tested_bits, injected_bits, drop_frames
);
 reg signed [15:0] gaussian_rom [0:4095];
 initial $readmemh("gaussian_q12.mem",gaussian_rom);
 reg signed [15:0] history [0:30];
 reg signed [15:0] echo_gain;
 reg [4:0] echo_delay;
 reg signed [31:0] echo_product,echo_value;
 integer h;
 reg enabled;
 reg [15:0] sigma, gain;
 reg [31:0] rng;
 reg [3:0] phase;
 reg signed [16:0] sine_rom[0:255];
 initial $readmemh("sine_q15.mem",sine_rom);
 reg [31:0] phase_acc,step;
 reg [1:0] compensate;
 reg [5:0] pilots_left; reg prepared,pilot_hold,first_hold;
 reg signed [31:0] sample_i,sample_q;
 wire pilot_decision; wire signed [37:0] estimate_i,estimate_q;
 pilot_receiver estimator(.clk(clk),.rst_n(rst_n),.clear(clear),.valid(phase==8),.pilot(pilot_hold),.first_pilot(first_hold),.sample_i(sample_i),.sample_q(sample_q),.decision(pilot_decision),.estimate_i(estimate_i),.estimate_q(estimate_q));
 reg signed [16:0] cosine,sine;
 reg [31:0] echo_acc,echo_delta,fade_acc0,fade_acc1,fade_delta0,fade_delta1;
 reg [15:0] depth0,depth1;
 wire [14:0] triangle0=fade_acc0[31]?~fade_acc0[30:16]:fade_acc0[30:16];
 wire [14:0] triangle1=fade_acc1[31]?~fade_acc1[30:16]:fade_acc1[30:16];
 reg [31:0] depth_product0,depth_product1;
 reg signed [16:0] factor0,factor1,echo_cos,echo_sin;
 reg signed [15:0] mapped_hold,delayed_hold;
 reg signed [48:0] atten0,atten1,echo_i,echo_q;
 reg signed [31:0] scaled0,scaled1;
 wire [7:0] echo_cos_addr=echo_acc[31:24]+8'd64;
 wire [7:0] cosine_address=phase_acc[31:24]+8'd64;
 reg signed [15:0] zq;
 reg signed [32:0] noise_q;
 reg signed [48:0] rotate_i,rotate_q,comp_i,comp_q;

 
 wire signed [49:0] compensated=$signed({comp_i[48],comp_i})+$signed({comp_q[48],comp_q});
 wire [31:0] rng_second=next_rng(rng);
 reg ref_bit, sop_hold, eop_hold;
 reg signed [15:0] z;
 reg signed [32:0] gain_product, noise_product;
 reg signed [31:0] signal_value;
 wire signed [31:0] base_value=signal_value+echo_value;
 wire signed [15:0] mapped;
 wire signed [31:0] received = (compensate==1) ? (compensated >>> 15) : sample_i;
 wire decision;
 bpsk_mod modulator(in_bit,mapped);
 bpsk_demod demodulator(received,decision);
 function automatic [31:0] next_rng(input [31:0] x);
  reg [31:0] t;
  begin t=x^(x<<13); t=t^(t>>17); next_rng=t^(t<<5); end
 endfunction
 assign lfsr_state=rng[15:0]; // Legacy debug port only; actual PRNG is xorshift32.
 assign in_ready=!clear && phase==0 && !out_valid && (!enabled || ((!in_sop || prepared) && pilots_left==0));
 always @(posedge clk) begin
  if(!rst_n) begin
   for(h=0;h<31;h=h+1) history[h]<=0;
   pilots_left<=0;prepared<=0;pilot_hold<=0;first_hold<=0;
   echo_acc<=0;echo_delta<=0;fade_acc0<=0;fade_acc1<=0;fade_delta0<=0;fade_delta1<=0;depth0<=0;depth1<=0;depth_product0<=0;depth_product1<=0;factor0<=32768;factor1<=32768;echo_cos<=0;echo_sin<=0;mapped_hold<=0;delayed_hold<=0;atten0<=0;atten1<=0;scaled0<=0;scaled1<=0;echo_i<=0;echo_q<=0;
   echo_gain<=0;echo_delay<=0;echo_product<=0;echo_value<=0;
   phase_acc<=0;step<=0;compensate<=0;cosine<=0;sine<=0;zq<=0;noise_q<=0;
   rotate_i<=0;rotate_q<=0;comp_i<=0;comp_q<=0;sample_i<=0;sample_q<=0;
   enabled<=0;sigma<=0;gain<=32768;rng<=1;phase<=0;
   out_valid<=0;out_bit<=0;out_sop<=0;out_eop<=0;
   ref_bit<=0;sop_hold<=0;eop_hold<=0;z<=0;
   gain_product<=0;noise_product<=0;signal_value<=0;
   tested_bits<=0;injected_bits<=0;drop_frames<=0;
  end else if(clear) begin
   for(h=0;h<31;h=h+1) history[h]<=0;
   pilots_left<=0;prepared<=0;pilot_hold<=0;first_hold<=0;
   echo_acc<=echo_initial;echo_delta<=echo_step;fade_acc0<=0;fade_acc1<=0;fade_delta0<=fade_step0;fade_delta1<=fade_step1;depth0<=fade_depth0;depth1<=fade_depth1;
   echo_gain<=echo_q14;echo_delay<=delay_symbols;echo_value<=0;echo_product<=0;
   phase_acc<=phase_initial;step<=phase_step;compensate<=ideal_compensation;
   enabled<=link_enable;sigma<=threshold;gain<=gain_q15;rng<={16'b0,seed};phase<=0;
   out_valid<=0;tested_bits<=0;injected_bits<=0;drop_frames<=0;
  end else begin
   if(out_valid && out_ready) begin
    out_valid<=0;
    tested_bits<=tested_bits+1;
    injected_bits<=injected_bits+(out_bit!=ref_bit); // Measured BER numerator.
   end
   if(enabled && in_valid && in_sop && !prepared && pilots_left==0 && phase==0 && !out_valid) begin pilots_left<=32;prepared<=1;end
   if((in_valid && in_ready) || (pilots_left!=0 && phase==0 && !out_valid)) begin
    if(!enabled) begin if(in_eop) drop_frames<=drop_frames+1; end
    else begin
     pilot_hold<=pilots_left!=0;first_hold<=pilots_left==32;
     if(pilots_left==0) begin ref_bit<=in_bit;sop_hold<=in_sop;eop_hold<=in_eop;if(in_eop)prepared<=0;end
     for(h=30;h>0;h=h-1) history[h]<=history[h-1];
     history[0]<=pilots_left!=0?16'sd8192:mapped;
     delayed_hold<=$signed(echo_delay==0 ? (pilots_left!=0?16'sd8192:mapped) : history[echo_delay-1]);
     z<=gaussian_rom[rng[31:20]];zq<=gaussian_rom[rng_second[31:20]];
     sine<=sine_rom[phase_acc[31:24]];cosine<=sine_rom[cosine_address];
     phase_acc<=phase_acc+step;
     mapped_hold<=pilots_left!=0?16'sd8192:mapped;
     depth_product0<=depth0*triangle0;depth_product1<=depth1*triangle1;
     echo_cos<=sine_rom[echo_cos_addr];echo_sin<=sine_rom[echo_acc[31:24]];
     echo_acc<=echo_acc+echo_delta;fade_acc0<=fade_acc0+fade_delta0;fade_acc1<=fade_acc1+fade_delta1;
     rng<=next_rng(rng_second);phase<=1;
    end
   end
   if(phase==1) begin
    noise_product<=$signed(z)*$signed({1'b0,sigma});noise_q<=$signed(zq)*$signed({1'b0,sigma});
    factor0<=32768-(depth_product0>>15);factor1<=32768-(depth_product1>>15);phase<=2;
   end
   if(phase==2) begin
    gain_product<=$signed(mapped_hold)*$signed({1'b0,gain});echo_product<=$signed(delayed_hold)*$signed(echo_gain);phase<=3;
   end
   if(phase==3) begin signal_value<=gain_product>>>15;echo_value<=echo_product>>>14;phase<=4;end
   if(phase==4) begin atten0<=$signed(signal_value)*factor0;atten1<=$signed(echo_value)*factor1;phase<=5;end
   if(phase==5) begin scaled0<=atten0>>>15;scaled1<=atten1>>>15;phase<=6;end
   if(phase==6) begin
    rotate_i<=$signed(scaled0)*$signed(cosine);rotate_q<=$signed(scaled0)*$signed(sine);
    echo_i<=$signed(scaled1)*$signed(echo_cos);echo_q<=$signed(scaled1)*$signed(echo_sin);phase<=7;
   end
   if(phase==7) begin
    sample_i<=(rotate_i>>>15)+(echo_i>>>15)+(noise_product>>>12);
    sample_q<=(rotate_q>>>15)+(echo_q>>>15)+(noise_q>>>12);phase<=8;
   end
   if(phase==8) begin
    // Oracle uses direct-path phase only. Pilot estimator has no phase inputs.
    comp_i<=$signed(sample_i)*$signed(cosine);comp_q<=$signed(sample_q)*$signed(sine);phase<=9;
   end
   if(phase==9) begin
    if(pilot_hold) begin pilots_left<=pilots_left-1;end
    else begin out_bit<=compensate==2?pilot_decision:decision;out_sop<=sop_hold;out_eop<=eop_hold;out_valid<=1;end
    phase<=0;
   end
  end
 end
endmodule

