"""Reuse the AXI driver, but require full received-byte equality on noisy trials."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=(root/'tests/tb_payload.sv').read_text().split(' initial begin\n  #300000000;')[0]
base=base.replace('module tb_payload;', 'module tb_noise_link;')
body=r'''
 integer delivered=0,captured=0;reg[31:0]caps,posterr;
 initial begin #1000000000;$fatal(1,"noise simulation watchdog");end
 initial begin
  repeat(10)@(negedge clk);rst=1;repeat(5)@(negedge clk);
  for(n=1;n<=32;n=n+1)begin
   load(64,3,1000+n);wr('hc0,1,15);wr('h40,19661,15);wr('h44,2800,15);
   wr('h54,298261618,15);wr('h5c,214748,15);wr('h58,n,15);
   start;wait_done;rd('h64,caps);captured=captured+caps;
   if(v[2])begin verify(64,1000+n);delivered=delivered+1;end
   rd('hd8,posterr);
   $display("NOISE_TRIAL seed=%0d delivered_total=%0d captures=%0d result=%0d pre_errors=%0d origin=%0d",n,delivered,caps,dut.result_code,posterr,dut.receive_phy.origin);
  end
  $display("NOISE_SIM_SUMMARY trials=32 captured=%0d delivered=%0d",captured,delivered);
  if(delivered<29)$fatal(1,"Noise delivery below 90 percent");
  $display("NOISE_LINK_PASS");$finish;
 end
endmodule
'''
# Internal signal names are intentionally not needed for the acceptance result.
body=body.replace(',dut.receive_phy.origin','').replace(' origin=%0d','')
(root/'tests/tb_noise_link.sv').write_text(base+body)
