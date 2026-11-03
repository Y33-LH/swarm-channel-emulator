// Wildfire HaoYue 5-inch 800x480 RGB565 panel, 33 MHz, active-high sync.
module lcd_800(input wire lcd_ref, output wire tft_clk,
 output reg hsync, vsync, tft_de, output wire tft_bl, output reg [15:0] rgb_tft);
wire raw, feedback, fb, px, locked;
MMCME2_BASE #(.CLKIN1_PERIOD(20.0), .CLKFBOUT_MULT_F(16.5), .DIVCLK_DIVIDE(1),
 .CLKOUT0_DIVIDE_F(25.0)) mm(.CLKIN1(lcd_ref),.RST(1'b0),.PWRDWN(1'b0),
 .CLKFBOUT(feedback),.CLKFBIN(fb),.CLKOUT0(raw),.LOCKED(locked));
BUFG fb_buf(.I(feedback),.O(fb));
BUFG px_buf(.I(raw),.O(px));
// Match the panel vendor's forwarded clock polarity. Pixel outputs launch on px rising.
ODDR #(.DDR_CLK_EDGE("SAME_EDGE")) forward_clock(.C(px),.CE(1'b1),.D1(1'b1),.D2(1'b0),.R(1'b0),.S(1'b0),.Q(tft_clk));
(* ASYNC_REG="TRUE" *) reg [2:0] ready=0;
always @(posedge px) ready <= {ready[1:0],locked};
reg [10:0] x=0; reg [9:0] y=0;
reg backlight=0;
assign tft_bl=backlight;
always @(posedge px) begin
 if(!ready[2]) backlight<=0;
 else if(x==1089 && y==534) backlight<=1;
end
always @(posedge px) begin
 if(!ready[2]) begin x<=0; y<=0; end
 else if(x==1089) begin x<=0; y<=y==534?0:y+1'b1; end else x<=x+1'b1;
end
// Safe title area for the supplied panel. Some controllers crop the input raster.
wire inside_logo=(x>=126 && x<510 && y>=124 && y<188);
wire [8:0] col=x-126; wire [5:0] row=y-124;
wire [14:0] addr={row,8'b0}+{row,7'b0}+col;
(* rom_style="block" *) reg [3:0] image[0:24575];
initial $readmemh("lcd_banner.mem",image);
// Convert the artwork palette at elaboration, keeping all three RGB565 channels.
function [15:0] color565(input [23:0] color);
 color565={color[23:19],color[15:10],color[7:3]};
endfunction
localparam [15:0] BACKGROUND=color565(24'h081018);
reg [3:0] ink; reg logo,subtitle,de0,hs0,vs0;
always @(posedge px) begin
 ink<=image[inside_logo ? addr : 15'd0]; logo<=inside_logo;
 subtitle<=row>=39 && row<=53;
 de0<=x>=80 && x<880 && y>=33 && y<513; hs0<=x<34; vs0<=y<10;
 tft_de<=de0; hsync<=hs0; vsync<=vs0;
 if(!logo) rgb_tft<=BACKGROUND;
 else case(ink)
 4'd0:  rgb_tft<=BACKGROUND;
 4'd1:  rgb_tft<=subtitle ? color565(24'h617987) : color565(24'h26404e);
 4'd2:  rgb_tft<=subtitle ? color565(24'hbdd3df) : color565(24'h5893a3);
 4'd3:  rgb_tft<=subtitle ? color565(24'hf0f6f8) : color565(24'h83c9d5);
 4'd4:  rgb_tft<=color565(24'hf7ffff);
 4'd5:  rgb_tft<=color565(24'hadc9e0);
 4'd6:  rgb_tft<=color565(24'hf7fbff);
 4'd7:  rgb_tft<=subtitle ? color565(24'hdfedf2) : color565(24'h79b6c2);
 4'd8:  rgb_tft<=color565(24'hd4faff);
 4'd9:  rgb_tft<=color565(24'he4ffff);
 4'd10: rgb_tft<=color565(24'hffffff);
 4'd11: rgb_tft<=color565(24'h956717);
 4'd12: rgb_tft<=color565(24'h543817);
 4'd13: rgb_tft<=color565(24'hffc744);
 4'd14: rgb_tft<=color565(24'h50e3ad);
 default: rgb_tft<=color565(24'hffffff);
 endcase
end
endmodule
