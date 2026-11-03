`timescale 1ns/1ps
module tb_channel_model;
 reg clk=0;always #8 clk=~clk;
 reg rst_n=0,clear=0,enable=0,accept_enable=1,suppress=0;
 reg[15:0]gain=32768,sigma=0,echo_gain=0;
 reg[9:0]delay=0;reg[5:0]echo_delay=0;
 reg[31:0]phase=0,step=0,seed=1,echo_phase=0,echo_step=0;
 reg signed[31:0]ramp=0,echo_ramp=0;
 reg[3:0]tap_count=0;reg[127:0]tap_gains=0;reg[79:0]tap_delays=0;reg[255:0]tap_phases=0,tap_steps=0,tap_ramps=0;
 integer f,c=-1,n=0,received=0,tick=0,j;
 wire tx_ready;
 two_path_link dut(.clk(clk),.rst_n(rst_n),.clear(clear),.enable(enable),.accept_enable(accept_enable),.ack_frame(1'b0),.fec_enable(1'b1),.hard_profile(1'b0),
 .tap_count(tap_count),.tap_gains(tap_gains),.tap_delays(tap_delays),.tap_phases(tap_phases),.tap_steps(tap_steps),.tap_ramps(tap_ramps),
 .gain_q15(gain),.sigma(sigma),.echo_gain(echo_gain),.start_delay(11'd17),.geometric_delay(delay),.echo_delay(echo_delay),.initial_phase(phase),.phase_step(step),.seed(seed),.echo_phase(echo_phase),.echo_step(echo_step),.gain_delta(ramp),.echo_gain_delta(echo_ramp),.suppress(suppress),.tx_valid(1'b1),.tx_bit(1'b1),.tx_ready(tx_ready),.rx_ready(1'b1),.trace_addr(9'd0),.trace_equalized(1'b0));
 // Channel-only harness: the receiver is not the authority for how many
 // samples are tested. Its consumer readiness is held high intentionally.
 initial begin force dut.in_ready=1'b1;force dut.window_done=1'b0;end
 always @(posedge clk)if(rst_n&&!clear&&c>=0)begin
  if(dut.advance)begin $fwrite(f,"S %0d %0d %0d\n",c,n,$signed(dut.source));n=n+1;end
  if(dut.pipe_valid[5]&&dut.pipe_ce)begin $fwrite(f,"Y %0d %0d %0d %0d\n",c,received,$signed(dut.sample_i),$signed(dut.sample_q));received=received+1;end
 end
 initial begin
  f=$fopen("channel_samples.txt","w");repeat(5)@(negedge clk);rst_n=1;
  for(c=0;c<14;c=c+1)begin
   clear=1;enable=0;accept_enable=1;n=0;received=0;
   gain=32768;echo_gain=0;sigma=0;phase=0;step=0;seed=723;delay=0;echo_delay=0;echo_phase=0;echo_step=0;ramp=0;echo_ramp=0;suppress=0;
   tap_count=0;tap_gains=0;tap_delays=0;tap_phases=0;tap_steps=0;tap_ramps=0;
   case(c)
    1:begin gain=19661;phase=32'h20000000;delay=37;end
    2,6,7:begin gain=24576;echo_gain=8192;phase=32'h12345678;echo_phase=32'h60000000;step=805306;echo_step=-536871;delay=53;echo_delay=8;end
    3:begin gain=24576;echo_gain=4096;ramp=-4096;echo_ramp=4096;phase=32'h40000000;echo_phase=32'hc0000000;delay=128;echo_delay=32;end
    4,8,9:begin suppress=1;sigma=1500;seed=c==4?723:c==8?7747:9973;end
    5:begin gain=32768;echo_gain=32768;sigma=20000;end
   endcase
   $fwrite(f,"C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n",c,gain,echo_gain,sigma,phase,step,seed,delay,echo_delay,echo_phase,echo_step,ramp,echo_ramp,suppress);
   if(c>=10)begin
    tap_count=c==10?1:c==13?3:8;
    for(j=0;j<tap_count;j=j+1)begin
     tap_gains[j*16+:16]=32768/(j+1);tap_delays[j*10+:10]=j==7?1023:j*7;
     tap_phases[j*32+:32]=j*32'h0712a357;tap_steps[j*32+:32]=(j%2?-1:1)*j*123456;
     tap_ramps[j*32+:32]=(j%2?-321:123);
     $fwrite(f,"M %0d %0d %0d %0d %0d %0d %0d\n",c,j,tap_gains[j*16+:16],tap_delays[j*10+:10],tap_phases[j*32+:32],tap_steps[j*32+:32],$signed(tap_ramps[j*32+:32]));
    end
   end
   repeat(3)@(negedge clk);clear=0;enable=1;
   while(n<50000)begin @(negedge clk);tick=tick+1;accept_enable=(c!=7&&c!=12)||((tick%7)!=0&&(tick%11)!=0);end
   enable=0;accept_enable=1;repeat(8)@(negedge clk);
   if(received!=n)$fatal(1,"Channel input/output count mismatch");
  end
  $fclose(f);$display("CHANNEL_MODEL_SAMPLES cases=14 samples=700000");$finish;
 end
 initial begin #20000000;$fatal(1,"channel watchdog");end
endmodule
