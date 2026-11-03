// Restoring divider. Used once per frame for measured channel inversion.
module div_u64(input wire clk,rst_n,start,input wire[63:0]numerator,input wire[31:0]denominator,output reg done,output reg[63:0]quotient);
 reg[63:0]q;reg[32:0]r;reg[31:0]d;reg[6:0]k;reg busy;
 wire[32:0]trial={r[31:0],q[63]};wire ge=trial>={1'b0,d};wire[63:0]qn={q[62:0],ge};
 always @(posedge clk)begin
  if(!rst_n)begin q<=0;r<=0;d<=1;k<=0;busy<=0;done<=0;quotient<=0;end
  else begin done<=0;
   if(start)begin q<=numerator;r<=0;d<=denominator==0?1:denominator;k<=0;busy<=1;end
   else if(busy)begin r<=ge?trial-d:trial;q<=qn;if(k==63)begin quotient<=qn;done<=1;busy<=0;end else k<=k+1;end
  end
 end
endmodule
