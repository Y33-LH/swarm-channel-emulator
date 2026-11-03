// Sample-level baseline link. Idle/delayed samples and noise enter RX normally.
// All state advances on a sample transaction, never on elapsed UI/wall time.
module dbpsk_sample_link(
 input wire clk,rst_n,clear,enable,accept_enable,
 input wire [15:0] gain_q15,sigma,
 input wire [10:0] start_delay,
 input wire [31:0] initial_phase,phase_step,seed,
 input wire suppress,
 input wire tx_valid,tx_bit,output wire tx_ready,
 output wire rx_valid,rx_bit,rx_sop,rx_eop,input wire rx_ready,
 output reg window_done,output wire [31:0] captures,rx_samples,sync_errors
);
 reg signed [15:0] gaussian[0:4095];initial $readmemh("gaussian_q12.mem",gaussian);
 reg signed [16:0] sine[0:255];initial $readmemh("sine_q15.mem",sine);
 reg [2:0] stage;reg [31:0] phase,rng;
 wire signed [15:0] source;wire [31:0] samples;
 wire advance=enable&&accept_enable&&!clear&&stage==0&&!window_done;
 dbpsk_wave_tx tx(.clk(clk),.rst_n(rst_n),.clear(clear),.advance(advance),.suppress(suppress),.start_delay(start_delay),.payload_valid(tx_valid),.payload_bit(tx_bit),.payload_ready(tx_ready),.sample_i(source),.sample_count(samples));
 function automatic [31:0] random_next(input [31:0] x);reg[31:0]t;begin t=x^(x<<13);t=t^(t>>17);random_next=t^(t<<5);end endfunction
 wire [31:0] rng2=random_next(rng);
 wire [7:0] ca=phase[31:24]+8'd64;
 reg signed [16:0] co,si;
 reg signed [32:0] scaled,noise_i,noise_q;
 reg signed [48:0] rot_i,rot_q;
 reg signed [15:0] sample_i,sample_q;
 wire in_ready;
 wire signed [49:0] sum_i=(rot_i>>>30)+(noise_i>>>12);
 wire signed [49:0] sum_q=(rot_q>>>30)+(noise_q>>>12);
 function automatic signed [15:0] saturate(input signed [49:0] v);begin saturate=v>32767?16'sd32767:v< -32768?-16'sd32768:v[15:0];end endfunction
 dbpsk_capture receiver(.clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(stage==4&&accept_enable),.in_i(sample_i),.in_q(sample_q),.in_ready(in_ready),.valid(rx_valid),.data_bit(rx_bit),.sop(rx_sop),.eop(rx_eop),.ready(rx_ready),.captures(captures),.search_samples(rx_samples),.sync_errors(sync_errors),.acquired());
 always @(posedge clk)begin
  if(!rst_n)begin stage<=0;phase<=0;rng<=1;co<=0;si<=0;scaled<=0;noise_i<=0;noise_q<=0;rot_i<=0;rot_q<=0;sample_i<=0;sample_q<=0;window_done<=0;end
  else if(clear)begin stage<=0;phase<=initial_phase;rng<=seed==0?1:seed;window_done<=0;end
  else begin
   if(advance)begin
    scaled<=$signed(source)*$signed({1'b0,gain_q15});co<=sine[ca];si<=sine[phase[31:24]];
    noise_i<=$signed(gaussian[rng[31:20]])*$signed({1'b0,sigma});noise_q<=$signed(gaussian[rng2[31:20]])*$signed({1'b0,sigma});
    rng<=random_next(rng2);phase<=phase+phase_step;stage<=1;
   end
   if(stage==1)begin rot_i<=$signed(scaled)*$signed(co);rot_q<=$signed(scaled)*$signed(si);stage<=2;end
   if(stage==2)begin sample_i<=saturate(sum_i);sample_q<=saturate(sum_q);stage<=3;end
   if(stage==3)stage<=4;
   if(stage==4&&in_ready&&accept_enable)begin stage<=0;if(samples>=8192)window_done<=1;end
  end
 end
endmodule
