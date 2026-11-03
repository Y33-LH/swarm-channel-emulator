`timescale 1ns/1ps
module tb_mixed_nodes;
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

 task hn_wait(input[11:0]base);integer guard;begin guard=0;rd(base+'h40,v);while(v[0]&&guard<1000)begin rd(base+'h40,v);guard++;end ck(!v[0],"hardware node completes");expect_reg(base+'h88,0);end endtask
 task rawload;begin for(integer k=0;k<24;k++)wr('h100+k*4,{frame[k*4+3],frame[k*4+2],frame[k*4+1],frame[k*4]},15);end endtask
 task setup_node(input[11:0]base);begin wr(base,1,15);wr(base+4,77,15);wr(base+8,0,15);wr(base+12,1250000,15);wr(base+16,2150000,15);wr(base+20,400000,15);wr(base+24,1,15);wr(base,2,15);hn_wait(base);expect_reg(base+'h44,1);end endtask
 initial begin #100000000;$fatal(1,"MIXED_WATCHDOG");end
 initial begin
  repeat(10)@(negedge clk);rst=1;repeat(5)@(negedge clk);
  setup_node('h400);setup_node('h800);
  wr('h400,3,15);hn_wait('h400);wr(4,16,15);wr(8,32'h80000001,15);wr('h304,1,15);wr('hc0,1,15);
  start;wait_done;ck(v[2],"PL node DATA through real PHY");expect_reg('h20,784);expect_reg('ha0,0);
  for(i=0;i<24;i++)begin rd('h500+i*4,q);expect_reg('h200+i*4,q);end
  expect_reg('h444,1);expect_reg('h844,1);
  // ACK returns through the same real modem/channel/decoder before dequeue.
  wr(0,4,15);wr('h304,0,15);wr('h74,1,15);wr(4,12,15);
  for(i=0;i<96;i++)frame[i]=0;frame[0]=77;frame[4]=1;frame[7]='h80;frame[10]=10;rawload();
  start;wait_done;ck(v[2],"ACK through real PHY");expect_reg('h454,1);expect_reg('h4a0,0);expect_reg('h8a0,1);
  // A downlink command changes node9; node13 stays at the original period.
  wr(0,4,15);wr('h74,0,15);wr(4,16,15);wr('h304,0,15);
  for(i=0;i<96;i++)frame[i]=0;
  frame[0]=1;frame[1]=6;frame[3]=5;frame[5]=9;frame[6]=10;frame[7]=9;frame[8]=77;frame[12]=101;frame[18]=1;frame[28]=16;
  frame[32]=1;frame[36]=2;frame[40]=200;frame[44]='h10;frame[45]='h27;rawload();start;wait_done;ck(v[2],"command decoded");hn_wait('h400);
  expect_reg('h468,200);expect_reg('h868,1000);expect_reg('h464,1);expect_reg('h864,0);
  // Hardware-generated ACK, no ARM ACK bytes are provided.
  wr(0,4,15);wr('h304,3,15);wr('h74,1,15);wr(4,12,15);start;wait_done;ck(v[2],"PL generated ACK decoded");
  expect_reg('h200,77);expect_reg('h204,101);expect_reg('h208,32'h00090000);
  wr(0,4,15);wr('h400,3,15);hn_wait('h400);wr('h304,1,15);wr('h74,0,15);wr(4,20,15);start;wait_done;ck(v[2],"actual execution result returned");expect_reg('h224,2);expect_reg('h228,200);
  // Per-node queue reset does not disturb the second endpoint or shared PHY.
  wr('h400,16,15);expect_reg('h4a0,0);expect_reg('h8a0,1);
  wr(0,4,15);wr('h800,3,15);hn_wait('h800);wr('h304,2,15);wr(4,16,15);start;wait_done;ck(v[2],"second endpoint independent DATA");expect_reg('h204,32'h0e0d000d);expect_reg('ha0,0);
  $display("MIXED_NODES_PHY_PASS checks=%0d starts=%0d",checks,total_starts);$finish;
 end
endmodule
