// Explicit AMD XPM block RAM; identical model in XSim and synthesis.
module sample_bram #(parameter A=15)(
 input wire clk,we,input wire[A-1:0]wa,ra,input wire[31:0]d,
 output wire[31:0]q
);
 xpm_memory_sdpram #(
  .MEMORY_SIZE((1<<A)*32),.MEMORY_PRIMITIVE("block"),
  .CLOCKING_MODE("common_clock"),.ECC_MODE("no_ecc"),.USE_MEM_INIT(0),
  .WRITE_DATA_WIDTH_A(32),.BYTE_WRITE_WIDTH_A(32),.ADDR_WIDTH_A(A),
  .READ_DATA_WIDTH_B(32),.ADDR_WIDTH_B(A),.READ_LATENCY_B(1),
  .WRITE_MODE_B("read_first")
 ) memory (
  .clka(clk),.ena(1'b1),.wea(we),.addra(wa),.dina(d),
  .clkb(clk),.enb(1'b1),.addrb(ra),.doutb(q),.regceb(1'b1),
  .rstb(1'b0),.sleep(1'b0),.injectsbiterra(1'b0),.injectdbiterra(1'b0),
  .sbiterrb(),.dbiterrb()
 );
endmodule
