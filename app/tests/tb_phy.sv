`timescale 1ns/1ps
module tb_phy;
 reg clk=0;always #10 clk=~clk;
 reg rst_n=0,clear=0,iv=0;reg signed[15:0]ii=0,qq=0;wire ir,lv,lr,failed,ov,ob,os,oe;
 wire signed[7:0]llr;wire[31:0]caps,nsamp,errors,cycles,updates,trace_count;wire signed[31:0]cfo,hi,hq,omega;
 wire[2:0]iterations;wire[12:0]idx;wire signed[15:0]ei,eq,ri,rq;wire dv;
 reg[31:0]iq[0:25999];reg bits[0:783],coded[0:4751];
 integer c,k,got=0,hard=0,clock_count=0,watchdog=0,j;reg sign_ref=0;real err_power=0,evm,expected_cfo,estimate;
 reg[14:0]trace_address=0;reg[1:0]trace_bank=1;wire[31:0]trace_word;
 phy_receiver rx(.hard_profile(c>=6),.clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(iv),.ack_frame(1'b0),.fec_enable(1'b1),.in_i(ii),.in_q(qq),.in_ready(ir),.valid(lv),.llr(llr),.ready(lr),.failed(failed),.captures(caps),.search_samples(nsamp),.sync_errors(errors),.training_i(),.training_q(),.training_energy(),.training_count(),.cfo_step(cfo),.channel_i(hi),.channel_q(hq),.timing_omega(omega),.timing_updates(updates),.bit_index(idx),.eq_i(ei),.eq_q(eq),.raw_i(ri),.raw_q(rq),.diagnostic_valid(dv),.trace_addr(trace_address),.trace_equalized(trace_bank),.trace_data(trace_word),.trace_count(trace_count));
 fec_decoder dec(.clk(clk),.rst_n(rst_n),.clear(clear),.ack_frame(1'b0),.fec_enable(1'b1),.in_valid(lv),.in_llr(llr),.in_ready(lr),.out_valid(ov),.out_bit(ob),.out_sop(os),.out_eop(oe),.out_ready(1'b1),.busy(),.decode_cycles(cycles),.iterations_done(iterations));
 always @(posedge clk)begin
  clock_count=clock_count+1;
  if(lv&&lr&&llr[7]!=coded[idx])hard=hard+1;
  if(dv)begin sign_ref=sign_ref^coded[idx];err_power=err_power+($itor(ei)-(sign_ref?-8192.0:8192.0))**2+$itor(eq)**2;
   if(c<3&&(idx<3||idx==100||idx==1000))$display("DBG c=%d idx=%d iq=%d,%d eq=%d,%d ref=%b rot=%h coef=%d,%d norm=%d,%d fb=%d,%d target=%h",c,idx,ri,rq,ei,eq,sign_ref,rx.rotation,rx.coef_i,rx.coef_q,rx.norm_i,rx.norm_q,rx.feedback_i,rx.feedback_q,rx.target);
  end
  if(ov)begin
   if(ob!==bits[got])begin $display("PHY_DECODE_FAIL case=%d bit=%d got=%b exp=%b CFO=%d omega=%d hard=%d h=%d,%d",c,got,ob,bits[got],cfo,omega,hard,hi,hq);$fatal;end
   got=got+1;
  end
  if(clock_count>4000000)$fatal(1,"watchdog");
 end
 initial begin
  $readmemh("bits.mem",bits);$readmemh("coded.mem",coded);
  repeat(4)@(negedge clk);rst_n=1;
  for(c=0;c<12;c=c+1)begin
   $readmemh($sformatf("iq_%0d.mem",c%6),iq);got=0;hard=0;sign_ref=0;err_power=0;
   clear=1;@(negedge clk);clear=0;
   k=0;while(k<26000&&ir)begin iv=1;ii=iq[k][15:0];qq=iq[k][31:16];@(negedge clk);k=k+1;end
   iv=0;watchdog=0;
   while(got<784&&!failed&&watchdog<250000)begin @(negedge clk);watchdog=watchdog+1;end
   if(failed||got!=784)$fatal(1,"PHY_CAPTURE_FAIL case=%d got=%d state=%d",c,got,rx.state);
   evm=$sqrt(err_power/(4752.0*8192.0*8192.0))*100;
   case(c%6)0:expected_cfo=0;1:expected_cfo=5000;2:expected_cfo=-6000;3:expected_cfo=500;4:expected_cfo=1000;5:expected_cfo=-1500;endcase
   estimate=$itor(cfo)*8000000.0/4294967296.0;
   if(estimate-expected_cfo>80||estimate-expected_cfo< -80||evm>15)$fatal(1,"DSP metric qualification failed c=%d cfo=%f EVM=%f",c,estimate,evm);
   $display("PHY_CASE_PASS case=%d cfo_hz=%f omega=%d coded_errors=%d evm_percent=%f iterations=%d",c,$itor(cfo)*8000000.0/4294967296.0,omega,hard,evm,iterations);
   trace_bank=2;
   for(j=0;j<128;j=j+1)begin
    trace_address=3000+j;repeat(4)@(negedge clk);
    if(trace_word!==iq[3000+j])$fatal(1,"CONTINUOUS_TRACE_MISMATCH case=%d sample=%d",c,3000+j);
   end
   trace_bank=1;
   $display("CONTINUOUS_TRACE_PASS case=%d samples=128",c);
   repeat(3)@(negedge clk);
  end
  $display("PHY_ALL_PASS cases=12 profiles=2");$finish;
 end
endmodule
