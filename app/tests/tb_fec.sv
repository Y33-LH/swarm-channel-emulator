`timescale 1ns/1ps
module tb_fec;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0,clear=0,ack=0,iv=0,ib=0,er=0,di=0,orr=1;
 reg signed[7:0] llr=0;wire ir,ev,eb,prepared,dir,ov,ob,os,oe,busy;wire[12:0] count;wire[31:0]cycles;wire[2:0]iterations;
 reg bits[0:783],coded[0:4751];reg signed[7:0] noise[0:4751];
 integer c,k,n,len,got,errors,hard_errors,total_hard=0,clock_count=0;
 fec_encoder enc(.clk(clk),.rst_n(rst_n),.clear(clear),.ack_frame(ack),.fec_enable(1'b1),.in_valid(iv),.in_bit(ib),.in_ready(ir),.out_valid(ev),.out_bit(eb),.out_ready(er),.prepared(prepared),.coded_length(count),.monitor_addr(13'd0),.monitor_bit());
 fec_decoder dec(.clk(clk),.rst_n(rst_n),.clear(clear),.ack_frame(ack),.fec_enable(1'b1),.in_valid(di),.in_llr(llr),.in_ready(dir),.out_valid(ov),.out_bit(ob),.out_sop(os),.out_eop(oe),.out_ready(orr),.busy(busy),.decode_cycles(cycles),.iterations_done(iterations));
 always @(posedge clk)begin
  clock_count=clock_count+1;
  if(ov&&orr)begin
   if(ob!==bits[got]||os!==(got==0)||oe!==(got==len-1))begin $display("DECODE_FAIL case=%d bit=%d got=%b exp=%b sop=%b eop=%b",c,got,ob,bits[got],os,oe);$fatal;end
   got=got+1;
  end
  if(clock_count>2000000)$fatal(1,"FEC watchdog");
 end
 initial begin
  repeat(4)@(negedge clk);rst_n=1;
  for(c=0;c<16;c=c+1)begin
   ack=c>=8;len=ack?112:784;n=ack?720:4752;got=0;hard_errors=0;
   $readmemh($sformatf("in_%0d.mem",c),bits,0,len-1);$readmemh($sformatf("coded_%0d.mem",c),coded,0,n-1);$readmemh($sformatf("llr_%0d.mem",c),noise,0,n-1);
   clear=1;@(negedge clk);clear=0;
   for(k=0;k<len;k=k+1)begin iv=1;ib=bits[k];@(negedge clk);end
   iv=0;wait(prepared);@(negedge clk);
   if(count!==n)$fatal(1,"length mismatch");
   for(k=0;k<n;k=k+1)begin
    if(!ev||eb!==coded[k])begin $display("ENCODE_FAIL case=%d bit=%d got=%b exp=%b",c,k,eb,coded[k]);$fatal;end
    er=1;di=1;llr=noise[k];if(llr[7]!=coded[k])hard_errors=hard_errors+1;@(negedge clk);
   end
   er=0;di=0;
   // Backpressure the decoded stream repeatedly, including its last word.
   while(got<len)begin orr=(clock_count%7)!=0;@(negedge clk);end
   orr=1;if(iterations!=2)$fatal(1,"not full iterative Turbo");
   total_hard=total_hard+hard_errors;
   $display("FEC_CASE_PASS case=%0d input=%0d coded=%0d hard_errors=%0d decoded_errors=0 iterations=%0d cycles=%0d",c,len,n,hard_errors,iterations,cycles);
   repeat(3)@(negedge clk);
  end
  if(total_hard==0)$fatal(1,"No correction exercised");
  $display("FEC_ALL_PASS cases=16");$finish;
 end
endmodule
