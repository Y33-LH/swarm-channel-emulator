`timescale 1ns/1ps
module tb_hardware_node;
 reg clk=0;always #8 clk=~clk;
 reg rst=0,bw=0;reg[9:0]ba=0,ra=0;reg[31:0]bd=0;reg[3:0]strb=15;
 reg phy_busy=0,launch=0,rw=0,commit=0,good=0,ack=0;
 reg[6:0]idx=0,ti=0;reg[7:0]data=0;
 wire[31:0]rd,len,seq;wire[7:0]tb,ab;wire ready,ackready;
 hardware_node #(.NODE_ID(9)) dut(clk,rst,bw,ba,bd,strb,ra,rd,phy_busy,launch,rw,idx,data,commit,good,ack,ti,tb,ab,ready,len,seq,ackready);
 reg[7:0]rx[0:95],saved[0:95];integer checks=0,k;reg[31:0]firstseq;
 task ck(input bit b,input string msg);begin checks++;if(!b)$fatal(1,"NODE_FAIL %s at %t",msg,$time);end endtask
 task wr(input[9:0]a,input[31:0]d);begin @(negedge clk);ba=a;bd=d;bw=1;@(negedge clk);bw=0;end endtask
 task idle;integer guard;begin ra='h40;#1;guard=0;while(rd[0]&&guard<10000)begin @(negedge clk);guard++;end ck(!rd[0],"bounded endpoint work");end endtask
 task eq(input[9:0]a,input[31:0]d);begin ra=a;#1;if(rd!==d)$display("addr=%h got=%h expected=%h",a,rd,d);ck(rd===d,"register");end endtask
 task tick(input integer r);begin idle();wr(8,r);wr(0,2);idle();end endtask
 task select_tx;begin wr(0,3);idle();end endtask
 task zero_rx;begin for(integer j=0;j<96;j++)rx[j]=0;end endtask
 task put32(input integer off,input[31:0]v);begin for(integer j=0;j<4;j++)rx[off+j]=v>>(8*j);end endtask
 task receive(input bit is_ack,crc_good);begin
  for(integer j=0;j<(is_ack?12:96);j++)begin @(negedge clk);rw=1;idx=j;data=rx[j];end
  @(negedge clk);rw=0;ack=is_ack;good=crc_good;commit=1;
  @(negedge clk);commit=0;idle();
 end endtask
 task ack_tx;begin zero_rx();put32(0,77);put32(4,seq);rx[10]=10;receive(1,1);end endtask
 task command(input[31:0]id,input[7:0]op,input[31:0]value,expiry);begin
  zero_rx();rx[0]=1;rx[1]=6;rx[3]=5;rx[5]=9;rx[6]=10;rx[7]=9;
  put32(8,77);put32(12,id+1000);rx[18]=1;rx[28]=16;
  put32(32,id);rx[36]=op;put32(40,value);put32(44,expiry);
 end endtask
 initial begin #10000000;$fatal(1,"NODE_WATCHDOG");end
 initial begin
  repeat(5)@(negedge clk);rst=1;
  wr(0,1);wr(4,77);wr('hc,1250000);wr('h10,2150000);wr('h14,400000);wr('h18,1);
  tick(0);eq('h44,1);eq('ha0,1);select_tx();ck(ready&&len==16,"autonomous heartbeat ready");firstseq=seq;
  for(k=0;k<96;k++)begin ti=k;#1;saved[k]=tb;end
  ck(saved[4]==9&&saved[6]==9&&saved[7]==10&&saved[1]==1,"node-owned header");
  ck({saved[35],saved[34],saved[33],saved[32]}==1250000,"position snapshot");
  // Failed ACK cannot release a packet; retry is byte-identical except attempt.
  zero_rx();put32(0,77);put32(4,seq);rx[10]=10;receive(1,0);ck(ready,"CRC-failed ACK retained");
  wr(0,4);tick(1);select_tx();ck(ready&&seq==firstseq,"retry preserves identity");
  for(k=0;k<96;k++)begin ti=k;#1;ck(tb==(k==30?8'd1:saved[k]),"retry data unchanged");end
  ack_tx();ck(!ready,"actual valid ACK releases");eq('h54,1);eq('h58,1);
  tick(2);eq('h44,1);tick(10);eq('h44,2);select_tx();ack_tx();
  // Only received commands mutate the endpoint. Reject corrupt and wrong run.
  command(1,2,200,10000);receive(0,0);eq('h68,1000);eq('h64,0);
  put32(8,78);receive(0,1);eq('h64,0);put32(8,77);receive(0,1);
  eq('h68,200);eq('h64,1);eq('h84,1);eq('h48,1);ck(ackready,"command ACK generated in PL");
  select_tx();ck(ready&&len==20,"execution response queued");ti=36;#1;ck(tb==2,"actual response status");ack_tx();
  receive(0,1); // previous buffer is ACK, must not execute as command
  command(1,2,200,10000);receive(0,1);eq('h64,1);eq('h60,1);eq('h48,1);
  command(2,5,450,10000);receive(0,1);eq('h74,450);eq('h90,1);select_tx();ack_tx();
  command(3,5,700,10000);receive(0,1);eq('h74,450);select_tx();ti=36;#1;ck(tb==3,"unsafe height rejected");ack_tx();
  command(4,1,0,1);receive(0,1);select_tx();ti=36;#1;ck(tb==4,"expired command result");ack_tx();
  tick(12);eq('h44,3);select_tx();ack_tx();
  wr('h18,0);tick(14);eq('h44,3);wr('h18,1);tick(16);eq('h44,4);
  wr(0,16);eq('ha0,0);eq('h98,1);tick(18);eq('h44,5);
  // Endpoints reject malformed MMIO and do not allow byte writes to controls.
  strb=1;wr('h18,0);strb=15;eq('h88,8);eq('h18,1);wr(0,5);
  tick(18);eq('h88,10);wr(0,5);
  // Full queues are bounded and failures counted, not silently overwritten.
  wr(0,1);wr('h1c,100);
  for(k=0;k<20;k++)tick(k);
  eq('ha0,128);ra='h50;#1;ck(rd>0,"queue overflow counted");
  tick(700);select_tx();eq('ha0,0);eq('h5c,128);
  $display("HARDWARE_NODE_UNIT_PASS checks=%0d",checks);$finish;
 end
endmodule
