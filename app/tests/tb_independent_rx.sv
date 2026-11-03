`timescale 1ns/1ps
module tb_independent_rx;
 reg clk=0;always #10 clk=~clk;
 reg rst=0,clear=0,iv=0,ready=1;reg signed[15:0]ii=0,iq=0;
 wire ir,ov,ob,os,oe;wire[31:0]caps,samples,errs;
 reg[31:0] vectors[0:196607];reg[7:0] expected[0:2351];
 integer c,n,bits_seen=0,checks=0,tick=0;
 dbpsk_capture dut(.clk(clk),.rst_n(rst),.clear(clear),.ack_frame(1'b0),.in_valid(iv),.in_i(ii),.in_q(iq),.in_ready(ir),.valid(ov),.data_bit(ob),.sop(os),.eop(oe),.ready(ready),.captures(caps),.search_samples(samples),.sync_errors(errs),.acquired());
 always @(negedge clk)begin tick=tick+1;ready=(tick%7)!=0;end
 always @(posedge clk)if(rst&&!clear&&ov&&ready)begin
  if(c>=16)$fatal(1,"False acquisition case %0d",c);
  if(ob!==expected[c*98+bits_seen/8][7-(bits_seen%8)])$fatal(1,"RX bit mismatch case=%0d bit=%0d",c,bits_seen);
  if(os!==(bits_seen==0)||oe!==(bits_seen==783))$fatal(1,"RX boundary mismatch");
  bits_seen=bits_seen+1;checks=checks+1;
 end
 initial begin
  $readmemh("receiver_vectors.mem",vectors);$readmemh("receiver_expected.mem",expected);
  repeat(5)@(negedge clk);rst=1;
  for(c=0;c<24;c=c+1)begin
   @(negedge clk);clear=1;iv=0;@(negedge clk);clear=0;bits_seen=0;
   for(n=0;n<8192;n=n+1)begin
    @(negedge clk);iv=1;ii=vectors[c*8192+n][15:0];iq=vectors[c*8192+n][31:16];
    do @(posedge clk);while(!ir);
    @(negedge clk);iv=0;
    if(n%17==0)repeat(2)@(negedge clk);
   end
   repeat(10)@(negedge clk);
   if(bits_seen!=(c<16?784:0)||caps!=(c<16?1:0))$fatal(1,"count mismatch case=%0d bits=%0d caps=%0d",c,bits_seen,caps);
  end
  $display("INDEPENDENT_RX_PASS cases=24 compared_bits=%0d",checks);$finish;
 end
 initial begin #100000000;$fatal(1,"watchdog");end
endmodule
