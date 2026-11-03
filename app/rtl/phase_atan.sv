// Iterative vectoring CORDIC, binary turns: 2^32 represents 2*pi.
module phase_atan(input wire clk,rst_n,start,input wire signed[63:0] xi,yi,output reg done,output reg signed[31:0] angle);
 reg signed[63:0]x,y;reg signed[31:0]z;reg[4:0]k;reg busy;
 function automatic signed[31:0] a(input[4:0]i);begin case(i)
  0:a=536870912;1:a=316933406;2:a=167458907;3:a=85004756;4:a=42667331;5:a=21354465;6:a=10679838;7:a=5340245;
  8:a=2670163;9:a=1335087;10:a=667544;11:a=333772;12:a=166886;13:a=83443;14:a=41722;15:a=20861;
  16:a=10430;17:a=5215;18:a=2608;19:a=1304;20:a=652;21:a=326;22:a=163;23:a=81;default:a=0;endcase end endfunction
 always @(posedge clk)begin
  if(!rst_n)begin x<=0;y<=0;z<=0;k<=0;busy<=0;done<=0;angle<=0;end
  else begin done<=0;
   if(start)begin x<=xi<0?-xi:xi;y<=xi<0?-yi:yi;z<=xi<0?32'sh80000000:0;k<=0;busy<=1;end
   else if(busy)begin
    if(y>0)begin x<=x+(y>>>k);y<=y-(x>>>k);z<=z+a(k);end
    else if(y<0)begin x<=x-(y>>>k);y<=y+(x>>>k);z<=z-a(k);end
    if(k==24)begin angle<=z;busy<=0;done<=1;end else k<=k+1;
   end
  end
 end
endmodule
