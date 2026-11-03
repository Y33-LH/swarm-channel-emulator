`timescale 1ns/1ps
module tb_payload;
 reg clk=0;always #10 clk=~clk;
 reg rst=0,accept_enable=1,gate=0;integer tick=0;
 always @(negedge clk)begin tick=tick+1;accept_enable=gate?((tick%7)!=0&&(tick%11)!=0):1;end
 reg [11:0] awaddr=0,araddr=0;reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
 reg [31:0] wdata=0;reg [3:0] wstrb=15;
 wire awready,wready,bvalid,arready,rvalid;wire [1:0]bresp,rresp;wire[31:0]rdata;
 axi_minimal dut(.aclk(clk),.aresetn(rst),.s_axi_awaddr(awaddr),.s_axi_awvalid(awvalid),.s_axi_awready(awready),.s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),.s_axi_araddr(araddr),.s_axi_arvalid(arvalid),.s_axi_arready(arready),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready),.accept_enable(accept_enable));
 integer checks=0,transfers=0,order=0,total_starts=0;reg[7:0] frame[0:95];reg[31:0]v,q;reg[15:0]ref_crc;integer i,j,n,pat,len,gen=0;
 task ck(input bit ok,input string msg);begin checks=checks+1;if(!ok)$fatal(1,"FAIL %s at %t",msg,$time);end endtask
 task wa(input[11:0]a);begin @(negedge clk);awaddr=a;awvalid=1;do @(posedge clk);while(!awready);@(negedge clk);awvalid=0;end endtask
 task wd(input[31:0]d,input[3:0]s);begin @(negedge clk);wdata=d;wstrb=s;wvalid=1;do @(posedge clk);while(!wready);@(negedge clk);wvalid=0;end endtask
 task wr(input[11:0]a,input[31:0]d,input[3:0]s);begin
  order=order+1;
  if(order%3==0)begin wd(d,s);repeat(2)@(negedge clk);wa(a);end
  else if(order%3==1)begin wa(a);repeat(3)@(negedge clk);wd(d,s);end
  else begin fork wa(a);wd(d,s);join end
  wait(bvalid);ck(bresp==0,"AXI write OKAY");repeat(2)begin @(negedge clk);ck(bvalid,"B held under backpressure");end
  bready=1;@(negedge clk);bready=0;
 end endtask
 task rd(input[11:0]a,output[31:0]d);reg[31:0]saved;begin
  @(negedge clk);araddr=a;arvalid=1;do @(posedge clk);while(!arready);@(negedge clk);arvalid=0;
  wait(rvalid);saved=rdata;ck(rresp==0,"AXI read OKAY");repeat(2)begin @(negedge clk);ck(rvalid&&rdata===saved,"R stable under backpressure");end
  d=saved;rready=1;@(negedge clk);rready=0;
 end endtask
 task expect_reg(input[11:0]a,input[31:0]exp);begin rd(a,v);if(v!==exp)$display("address=%h actual=%h expected=%h",a,v,exp);ck(v===exp,"register value");end endtask
 task make_frame(input integer length,pattern,seq);integer k;reg[31:0]rng;begin
  for(k=0;k<96;k=k+1)frame[k]=0;
  frame[0]=1;frame[1]=1;frame[3]=1;frame[4]=1;frame[6]=1;frame[8]=8'h13;
  frame[12]=seq;frame[13]=seq>>8;frame[18]=1;frame[28]=length;frame[29]=length>>8;
  rng=32'h12345678+seq;
  for(k=0;k<length&&k<64;k=k+1)begin
   rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
   case(pattern)0:frame[32+k]=0;1:frame[32+k]=255;2:frame[32+k]=(k%2)?8'h55:8'haa;default:frame[32+k]=rng[7:0];endcase
  end
  ref_crc=16'hffff;for(k=0;k<96;k=k+1)begin ref_crc=ref_crc^{frame[k],8'h00};for(integer b=0;b<8;b=b+1)ref_crc=ref_crc[15]?(ref_crc<<1)^16'h1021:ref_crc<<1;end
 end endtask
 task load(input integer length,pattern,seq);integer k;begin
  wr(0,4,15);make_frame(length,pattern,seq);wr(4,length,15);wr(8,seq,15);wr('hc,0,15);wr('h30,5000000,15);
  for(k=0;k<24;k=k+1)wr('h100+k*4,{frame[k*4+3],frame[k*4+2],frame[k*4+1],frame[k*4]},15);
 end endtask
 task start;begin wr(0,1,15);gen=gen+1;total_starts=total_starts+1;end endtask
 task wait_done;integer polls;begin
  v=0;polls=0;while(!v[1]&&polls<40000)begin repeat(10)@(negedge clk);rd('h10,v);polls=polls+1;end
  ck(v[1]&&!v[0],"terminal completion bounded");
 end endtask
 task verify(input integer length,seq);integer k;begin
  wait_done;ck(v[2]&&v[3]&&!v[5],"RX valid and CRC good");expect_reg('h14,0);expect_reg('h18,length);expect_reg('h1c,96);expect_reg('h20,784);expect_reg('h24,784);expect_reg('h2c,gen);expect_reg('h38,seq);expect_reg('h4c,{ref_crc,ref_crc});
  for(k=0;k<24;k=k+1)expect_reg('h200+k*4,{frame[k*4+3],frame[k*4+2],frame[k*4+1],frame[k*4]});
  transfers=transfers+1;
 end endtask
 initial begin
  #300000000;$fatal(1,"testbench watchdog");
 end
 initial begin
  repeat(10)@(negedge clk);rst=1;repeat(5)@(negedge clk);
  expect_reg('h3c,'h000d0004);expect_reg('h40,32768);expect_reg('h44,0);
  for(pat=0;pat<4;pat=pat+1)for(n=0;n<12;n=n+1)begin
   case(n)0:len=1;1:len=2;2:len=3;3:len=4;4:len=7;5:len=15;6:len=16;7:len=31;8:len=32;9:len=33;10:len=63;11:len=64;endcase
   gate=pat%2;load(len,pat,transfers+1);start;verify(len,transfers+1);
  end
  // Successful RX data is held until explicitly released.
  wr('h100,32'hdeadbeef,15);expect_reg('h34,2);wr(0,1,15);expect_reg('h34,2);verify(len,transfers); // repeated read of same result
  wr(0,4,15);expect_reg('h200,0);expect_reg('h34,9);
  wr(4,0,15);wr(0,1,15);expect_reg('h34,3);wr(4,65,15);wr(0,1,15);expect_reg('h34,3);
  wr(4,1,15);wr(0,1,15);expect_reg('h34,4);
  // One missing byte, followed by byte-enable repair; no cross-byte pollution.
  load(1,3,100);wr(0,4,15);wr(4,1,15);
  for(i=0;i<24;i=i+1)wr('h100+i*4,{frame[i*4+3],frame[i*4+2],frame[i*4+1],frame[i*4]},i==23?7:15);
  wr(0,1,15);expect_reg('h34,4);wr('h15c,{frame[95],24'hffffff},8);start;verify(1,100);
  load(64,3,101);wr(4,63,15);wr(0,1,15);expect_reg('h34,5);
  load(64,3,102);wr('h48,1,15);start;wr(0,1,15);expect_reg('h34,1);wr('h100,0,15);expect_reg('h34,1);wr(4,1,15);expect_reg('h34,1);wr(0,4,15);expect_reg('h34,1);wr(0,16,15);wr('h48,0,15);verify(64,102);
  // Deliberately corrupt transmitted CRC; data must not be exposed as good.
  load(64,3,103);wr('hc,1,15);start;wait_done;expect_reg('h14,1);expect_reg('h18,0);expect_reg('h1c,0);expect_reg('h200,0);expect_reg('h34,9);
  // Abort while receive backpressured, then immediately release and restart.
  load(64,3,104);start;q=0;while(q<256)rd('h24,q);ck(q<784,"partial frame reached");wr('h48,1,15);wr(0,8,15);expect_reg('h14,3);expect_reg('h18,0);expect_reg('h200,0);
  load(64,3,105);start;verify(64,105);
  load(64,3,106);wr('h48,1,15);wr('h30,150,15);start;wait_done;expect_reg('h14,4);expect_reg('h18,0);expect_reg('h200,0);
  load(64,3,107);start;verify(64,107);
  wr(0,4,15);wr('h200,1,15);expect_reg('h34,7);wr('h300,1,15);expect_reg('h34,8);wr('h101,1,15);expect_reg('h34,8);wr(0,3,15);expect_reg('h34,6);wr('h30,0,15);expect_reg('h34,10);wr('h48,2,15);expect_reg('h34,10);wr('h40,32769,15);expect_reg('h34,10);wr(0,16,15);expect_reg('h34,0);
  // Reset while partially receiving must discard all old ownership and data.
  load(64,3,108);start;q=0;while(q<256)rd('h24,q);
  @(negedge clk);rst=0;repeat(5)@(negedge clk);rst=1;gen=0;
  expect_reg('h10,0);expect_reg('h18,0);expect_reg('h200,0);expect_reg('h34,9);
  load(64,3,109);start;verify(64,109);
  // Unknown start sample, all four sample phases, arbitrary fixed rotation.
  for(n=0;n<16;n=n+1)begin
   load(64,3,200+n);wr('h50,n*61+((n%4)),15);wr('h54,n*32'h11111111,15);wr('h44,512,15);
   start;verify(64,200+n);expect_reg('h64,1);
  end
  // No emitted frame: zero and noise-only samples must not report a payload.
  for(n=0;n<4;n=n+1)begin
   load(64,3,300+n);wr('h60,1,15);wr('h44,n*1024,15);start;wait_done;
   ck(!v[2],"noise-only cannot publish RX payload");expect_reg('h64,0);expect_reg('h14,5);expect_reg('h68,26000);
  end
  load(64,3,400);wr('h60,0,15);wr('h44,0,15);wr('h50,0,15);wr('h54,0,15);start;verify(64,400);
  // Two paths with independent rotation, integer delay and amplitude ramp.
  for(n=0;n<8;n=n+1)begin
   load(64,3,500+n);wr('h70,n*31,15);wr('h78,4096,15);wr('h7c,n*4,15);
   wr('h80,n*32'h20000000,15);wr('h5c,53687,15);wr('h84,32'hffff2e49,15);wr('h88,32'hfffffe00,15);
   start;verify(64,500+n);expect_reg('ha0,0);
  end
  // Deep attenuation produces real receiver failure, no synthetic loss flag.
  load(64,3,600);wr('h40,0,15);wr('h78,0,15);wr('h44,2048,15);start;wait_done;ck(!v[2],"deep fade rejected");
  // Short ACK body has independent CRC and 112 transmitted bits.
  load(12,3,601);wr('h40,32768,15);wr('h44,0,15);wr('h70,0,15);wr('h5c,0,15);wr('h88,0,15);wr('h74,1,15);
  start;wait_done;$display("ACK status=%h result=%d TXbits=%d RXbits=%d crc=%h/%h class=%d",v,dut.result_code,dut.tx_bits,dut.rx_bits,dut.result_calc_crc,dut.result_recv_crc,dut.frame_class);ck(v[2],"ACK valid");expect_reg('h1c,12);expect_reg('h20,112);expect_reg('h24,112);
  for(i=0;i<3;i=i+1)expect_reg('h200+i*4,{frame[i*4+3],frame[i*4+2],frame[i*4+1],frame[i*4]});
  load(64,3,602);wr('h74,0,15);start;verify(64,602);
  for(pat=0;pat<4;pat=pat+1)begin
   load(64,pat,700+pat);wr('hc0,1,15);wr('h40,32768,15);wr('h44,pat==3?3000:0,15);wr('h78,0,15);wr('h5c,0,15);wr('h88,0,15);
   start;verify(64,700+pat);expect_reg('he4,2);expect_reg('hdc,4752);expect_reg('hf0,4752);expect_reg('h300,512);expect_reg('ha0,0);
   rd('hd8,q);$display("FULL_FEC_AXI_PASS pattern=%d pre_errors=%d post_errors=0",pat,q);
   if(pat==3)ck(q>0,"physical noisy samples exercised real correction");
   wr('hf4,0,15);wr('hf8,1,15);rd('hfc,q);ck(q!==32'hxxxxxxxx,"actual IQ trace readable");
  end
  load(12,3,800);wr('h74,1,15);wr('h44,0,15);start;wait_done;ck(v[2],"FEC ACK valid");expect_reg('he4,2);expect_reg('hdc,720);
  $display("PAYLOAD_AXI_PASS checks=%0d successful_reads=%0d accepted_starts=%0d",checks,transfers,total_starts);$finish;
 end
endmodule
