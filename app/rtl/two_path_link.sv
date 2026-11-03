// Each scheduled task restores its directed-link random state and absolute phase.
// Idle gaps exceed the channel memory; fill count masks stale BRAM contents.
module two_path_link(
 input wire clk,rst_n,clear,enable,accept_enable,ack_frame,fec_enable,hard_profile,
 input wire [15:0] gain_q15,sigma,echo_gain,
 input wire [10:0] start_delay,
 input wire [9:0] geometric_delay,
 input wire [5:0] echo_delay,
 input wire [31:0] initial_phase,phase_step,seed,echo_phase,echo_step,
 input wire signed [31:0] gain_delta,echo_gain_delta,
 // tap_count=0 preserves the independently qualified two-path register ABI.
 // 1..8 selects all taps exclusively from the new packed register bank.
 input wire [3:0] tap_count,
 input wire [127:0] tap_gains,
 input wire [79:0] tap_delays,
 input wire [255:0] tap_phases,tap_steps,tap_ramps,
 input wire suppress,
 input wire tx_valid,tx_bit,output wire tx_ready,
 output wire rx_valid,output wire signed[7:0]rx_llr,input wire rx_ready,
 output wire window_done,output wire [31:0] captures,rx_samples,sync_errors,
 output wire [31:0] final_rng,final_phase,final_echo_phase,
 output reg [31:0] clipping,
 output wire signed [31:0] training_i,training_q,
 output wire [63:0] training_energy,output wire [31:0] training_count,
 output wire signed[31:0]cfo_estimate,channel_i,channel_q,timing_omega,
 output wire[31:0]timing_updates,output wire[12:0]bit_index,
 output wire signed[15:0]eq_i,eq_q,raw_i,raw_q,output wire diagnostic_valid,
 input wire[14:0]trace_addr,input wire[1:0]trace_equalized,output wire[31:0]trace_data,trace_count,
 output wire[31:0]wave_origin
);
 reg signed [15:0] gaussian[0:4095];initial $readmemh("gaussian_q12.mem",gaussian);
 reg signed [16:0] sine[0:255];initial $readmemh("sine_q15.mem",sine);
 reg [5:0] pipe_valid;
 reg [31:0] rng;
 wire signed [15:0] source;wire [31:0] samples;
 wire in_ready;
 wire pipe_ce=accept_enable&&in_ready;
 wire advance=enable&&pipe_ce&&!clear&&!window_done;
 dbpsk_wave_tx tx(.clk(clk),.rst_n(rst_n),.clear(clear),.advance(advance),.suppress(suppress),.ack_frame(ack_frame),.fec_enable(fec_enable),.start_delay(start_delay),.payload_valid(tx_valid),.payload_bit(tx_bit),.payload_ready(tx_ready),.sample_i(source),.sample_count(samples));
 function automatic [31:0] random_next(input [31:0] x);reg[31:0]t;begin t=x^(x<<13);t=t^(t>>17);random_next=t^(t<<5);end endfunction
 wire [31:0] rng2=random_next(rng);
 function automatic signed [15:0] saturate(input signed [35:0] v);begin saturate=v>32767?16'sd32767:v< -32768?-16'sd32768:v[15:0];end endfunction
 function automatic [31:0] ramp(input [31:0] a,input signed [31:0] d);reg signed[33:0]v;begin v=$signed({1'b0,a})+$signed(d);ramp=v<0 ? 0 : v>34'sh080000000 ? 32'h80000000 : v[31:0];end endfunction
 function automatic signed [15:0] multiply_gain(input signed[15:0]v,input[15:0]g);reg signed[32:0]p;begin p=v*$signed({1'b0,g});multiply_gain=p>>>15;end endfunction
 wire signed [32:0] path_i[0:7],path_q[0:7];
 wire [31:0] path_phase[0:7];
 genvar k;
 generate for(k=0;k<8;k=k+1)begin: taps
  // One independent history read port per tap, inferred as synchronous BRAM.
  reg signed[15:0] history[0:1023];
  reg[15:0] gain_cfg;reg[9:0] delay_cfg;
  reg[31:0] phase_cfg,step_cfg;reg signed[31:0] ramp_cfg;
  always @* begin
   gain_cfg=0;delay_cfg=0;phase_cfg=0;step_cfg=0;ramp_cfg=0;
   if(tap_count>=1 && tap_count<=8)begin
    if(k<tap_count)begin gain_cfg=tap_gains[k*16+:16];delay_cfg=tap_delays[k*10+:10];phase_cfg=tap_phases[k*32+:32];step_cfg=tap_steps[k*32+:32];ramp_cfg=tap_ramps[k*32+:32];end
   end else if(k==0)begin gain_cfg=gain_q15;delay_cfg=geometric_delay;phase_cfg=initial_phase;step_cfg=phase_step;ramp_cfg=gain_delta;end
   else if(k==1)begin gain_cfg=echo_gain;delay_cfg=geometric_delay+echo_delay;phase_cfg=echo_phase;step_cfg=echo_step;ramp_cfg=echo_gain_delta;end
  end
  reg[31:0] phase,gain_acc;
  reg[15:0] gain_hold;
  reg signed[15:0] delayed,scaled;
  reg signed[16:0] co,si,co2,si2;
  reg signed[32:0] ri,rq;
  wire[9:0] address=samples[9:0]-delay_cfg;
  wire[7:0] ca=phase[31:24]+8'd64;
  assign path_i[k]=ri;assign path_q[k]=rq;assign path_phase[k]=phase;
  always @(posedge clk)if(advance)begin
   history[samples[9:0]]<=source;
   delayed<=samples<delay_cfg?16'sd0:delay_cfg==0?source:history[address];
  end
  always @(posedge clk)begin
   if(!rst_n)begin phase<=0;gain_acc<=0;gain_hold<=0;co<=0;si<=0;co2<=0;si2<=0;scaled<=0;ri<=0;rq<=0;end
   else if(clear)begin phase<=phase_cfg;gain_acc<={gain_cfg,16'b0};end
   else if(pipe_ce)begin
    if(advance)begin co<=sine[ca];si<=sine[phase[31:24]];phase<=phase+step_cfg;gain_hold<=gain_acc[31:16];gain_acc<=ramp(gain_acc,ramp_cfg);end
    if(pipe_valid[0])begin scaled<=multiply_gain(delayed,gain_hold);co2<=co;si2<=si;end
    if(pipe_valid[1])begin ri<=$signed(scaled)*$signed(co2);rq<=$signed(scaled)*$signed(si2);end
   end
  end
 end endgenerate
 reg signed[32:0] noise_i[0:4],noise_q[0:4];
 reg signed[35:0] pair_i[0:3],pair_q[0:3],quad_i[0:1],quad_q[0:1];
 reg signed[15:0] sample_i,sample_q;
 wire signed[35:0] sum_i=quad_i[0]+quad_i[1]+(noise_i[4]>>>12);
 wire signed[35:0] sum_q=quad_q[0]+quad_q[1]+(noise_q[4]>>>12);
 assign final_rng=rng;assign final_phase=path_phase[0];assign final_echo_phase=path_phase[1];
 phy_receiver receiver(.hard_profile(hard_profile),.clk(clk),.rst_n(rst_n),.clear(clear),.ack_frame(ack_frame),.fec_enable(fec_enable),.in_valid(pipe_valid[5]&&accept_enable),.in_i(sample_i),.in_q(sample_q),.in_ready(in_ready),.valid(rx_valid),.llr(rx_llr),.ready(rx_ready),.captures(captures),.search_samples(rx_samples),.sync_errors(sync_errors),.failed(window_done),.training_i(training_i),.training_q(training_q),.training_energy(training_energy),.training_count(training_count),.cfo_step(cfo_estimate),.channel_i(channel_i),.channel_q(channel_q),.timing_omega(timing_omega),.timing_updates(timing_updates),.bit_index(bit_index),.eq_i(eq_i),.eq_q(eq_q),.raw_i(raw_i),.raw_q(raw_q),.diagnostic_valid(diagnostic_valid),.trace_addr(trace_addr),.trace_equalized(trace_equalized),.trace_data(trace_data),.trace_count(trace_count),.wave_origin(wave_origin));
 integer j;
 always @(posedge clk)begin
  if(!rst_n)begin pipe_valid<=0;rng<=1;sample_i<=0;sample_q<=0;clipping<=0;end
  else if(clear)begin pipe_valid<=0;rng<=seed==0?1:seed;clipping<=0;end
  else if(pipe_ce)begin
   pipe_valid<={pipe_valid[4:0],advance};
   if(advance)begin noise_i[0]<=$signed(gaussian[rng[31:20]])*$signed({1'b0,sigma});noise_q[0]<=$signed(gaussian[rng2[31:20]])*$signed({1'b0,sigma});rng<=random_next(rng2);end
   for(j=1;j<5;j=j+1)if(pipe_valid[j-1])begin noise_i[j]<=noise_i[j-1];noise_q[j]<=noise_q[j-1];end
   if(pipe_valid[2])for(j=0;j<4;j=j+1)begin pair_i[j]<=($signed(path_i[2*j])>>>15)+($signed(path_i[2*j+1])>>>15);pair_q[j]<=($signed(path_q[2*j])>>>15)+($signed(path_q[2*j+1])>>>15);end
   if(pipe_valid[3])for(j=0;j<2;j=j+1)begin quad_i[j]<=pair_i[2*j]+pair_i[2*j+1];quad_q[j]<=pair_q[2*j]+pair_q[2*j+1];end
   if(pipe_valid[4])begin sample_i<=saturate(sum_i);sample_q<=saturate(sum_q);if(sum_i>32767||sum_i< -32768||sum_q>32767||sum_q< -32768)clipping<=clipping+1;end
  end
 end
endmodule
