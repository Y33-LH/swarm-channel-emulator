// Two full Max-Log-MAP Turbo iterations (four SISO passes), then terminated
// soft Viterbi K7, inverse transpose and PN9 descrambling. No TX reference input.
module fec_decoder(
 input wire clk,rst_n,clear,ack_frame,fec_enable,
 input wire in_valid,input wire signed[7:0] in_llr,output wire in_ready,
 output reg out_valid,out_bit,out_sop,out_eop,input wire out_ready,
 output reg busy,output reg [31:0] decode_cycles,output reg [2:0] iterations_done
);
 localparam signed [19:0] NEG=-20'sd400000;
 reg signed[7:0] sys[0:1582],pa[0:1582],pb[0:1582],tailb[0:2];
 reg signed[11:0] prior_a[0:1579],prior_b[0:1579],conv_soft[0:1579];
 reg[159:0] alpha_ram[0:1582];reg[159:0] alpha_row;
 reg signed[19:0] alpha[0:7],beta[0:7];
 reg[63:0] trace_ram[0:789];reg[63:0] trace_row;
 reg signed[23:0] vm[0:63];reg decoded[0:783];
 reg[10:0] pi_data[0:1579],pi_ack[0:235],inv_data[0:1579],inv_ack[0:235];
 initial begin $readmemh("turbo_data.mem",pi_data);$readmemh("turbo_ack.mem",pi_ack);$readmemh("turbo_data_inv.mem",inv_data);$readmemh("turbo_ack_inv.mem",inv_ack);end
 reg[4:0] state;reg[12:0] pos;reg[10:0] k;reg half,iteration;
 reg signed[12:0] sy,pr,ap;reg signed[11:0] vs0,vs1;
 reg[5:0] traceback_state;reg[8:0] scr;reg[10:0] out_index;
 wire[10:0] length=ack_frame?112:784,n=ack_frame?236:1580;
 wire[12:0] total=ack_frame?720:4752;
 wire[10:0] pi=ack_frame?pi_ack[k]:pi_data[k],inv=ack_frame?inv_ack[k]:inv_data[k];
 wire[10:0] ext=(k%8)*(length/8)+(k/8);
 assign in_ready=state==0&&(!out_valid||out_ready);
 function automatic integer ns(input integer s,u);begin ns=((u^((s>>1)&1)^(s&1))<<2)|(s>>1);end endfunction
 function automatic integer parity(input integer s,u);begin parity=u^((s>>1)&1)^((s>>2)&1);end endfunction
 function automatic signed[31:0] gamma(input integer s,u,input signed[12:0]ss,pp,aa);reg signed[31:0]v,w;begin v=$signed(ss)+$signed(aa);w=$signed(pp);gamma=(u?-v:v)+(parity(s,u)?-w:w);end endfunction
 function automatic signed[11:0] clip(input signed[31:0]x);begin clip=x>2047?12'sd2047:x< -2047?-12'sd2047:x[11:0];end endfunction
 reg signed[31:0] fa[0:7],bb[0:7],m0s[0:7],m1s[0:7],fmax,bmax,m0,m1,app,extval,tmp,branch;
 reg signed[31:0] fa_s[0:7],bb_s[0:7],m0_s[0:7],m1_s[0:7],app_s,ext_s,m0_max,m1_max;
 function automatic signed[31:0]mx(input signed[31:0]a,b);begin mx=a>b?a:b;end endfunction
 wire signed[31:0] fmax_s=mx(mx(mx(fa_s[0],fa_s[1]),mx(fa_s[2],fa_s[3])),mx(mx(fa_s[4],fa_s[5]),mx(fa_s[6],fa_s[7])));
 wire signed[31:0] bmax_s=mx(mx(mx(bb_s[0],bb_s[1]),mx(bb_s[2],bb_s[3])),mx(mx(bb_s[4],bb_s[5]),mx(bb_s[6],bb_s[7])));
 wire signed[31:0] zero_max=mx(mx(mx(m0_s[0],m0_s[1]),mx(m0_s[2],m0_s[3])),mx(mx(m0_s[4],m0_s[5]),mx(m0_s[6],m0_s[7])));
 wire signed[31:0] one_max=mx(mx(mx(m1_s[0],m1_s[1]),mx(m1_s[2],m1_s[3])),mx(mx(m1_s[4],m1_s[5]),mx(m1_s[6],m1_s[7])));
 reg[159:0] alpha_word;integer s,u,t;
 always @* begin
  alpha_word=0;
  for(s=0;s<8;s=s+1)begin fa[s]=-400000;bb[s]=-400000;m0s[s]=-400000;m1s[s]=-400000;alpha_word[s*20+:20]=alpha[s];end
  m0=-400000;m1=-400000;fmax=-400000;bmax=-400000;tmp=0;branch=0;
  for(s=0;s<8;s=s+1)begin
   for(u=0;u<2;u=u+1)begin
    branch=gamma(s,u,sy,pr,ap);
    tmp=alpha[s]<=NEG?-400000:$signed(alpha[s])+branch;
    if(tmp>fa[ns(s,u)])fa[ns(s,u)]=tmp;
    tmp=beta[ns(s,u)]<=NEG?-400000:$signed(beta[ns(s,u)])+branch;
    if(tmp>bb[s])bb[s]=tmp;
    if($signed(alpha_row[s*20+:20])<=NEG||beta[ns(s,u)]<=NEG)tmp=-400000;
    else tmp=$signed(alpha_row[s*20+:20])+$signed(beta[ns(s,u)])+branch;
    if(u==0)m0s[s]=tmp;
    if(u==1)m1s[s]=tmp;
   end
  end
  for(s=0;s<8;s=s+1)begin if(fa[s]>fmax)fmax=fa[s];if(bb[s]>bmax)bmax=bb[s];end
  app=(m0-m1)>>>1;extval=app-$signed(sy)-$signed(ap);
 end
 reg signed[31:0] va[0:63],vc0,vc1;reg[63:0] picks;integer v,p0,p1,q0,q1;
 always @* begin
  picks=0;vc0=0;vc1=0;p0=0;p1=0;q0=0;q1=0;
  for(v=0;v<64;v=v+1)begin
   p0=(v&31)*2;p1=p0+1;q0=((v>>5)<<6)|p0;q1=((v>>5)<<6)|p1;
   vc0=$signed(vm[p0])+((^(q0&'o171))?-$signed(vs0):$signed(vs0))+((^(q0&'o133))?-$signed(vs1):$signed(vs1));
   vc1=$signed(vm[p1])+((^(q1&'o171))?-$signed(vs0):$signed(vs0))+((^(q1&'o133))?-$signed(vs1):$signed(vs1));
   if(vm[p0]<=-24'sd4000000)vc0=-4000000;
   if(vm[p1]<=-24'sd4000000)vc1=-4000000;
   picks[v]=vc1>vc0;va[v]=vc1>vc0?vc1:vc0;
  end
 end
 wire[10:0] body_addr=pos/3;
 wire[10:0] ta=n+(pos-3*n)/2,tb=n+(pos-3*n-6)/2;
 wire[10:0] sys_wa=pos<3*n?body_addr:ta;
 wire[10:0] pa_wa=pos<3*n?body_addr:ta;
 wire[10:0] pb_wa=pos<3*n?body_addr:tb;
 wire input_accept=state==0&&in_valid&&in_ready&&fec_enable;
 wire sys_we=input_accept&&((pos<3*n&&pos%3==0)||(pos>=3*n&&pos<3*n+6&&(pos-3*n)%2==0));
 wire pa_we=input_accept&&((pos<3*n&&pos%3==1)||(pos>=3*n&&pos<3*n+6&&(pos-3*n)%2==1));
 wire pb_we=input_accept&&((pos<3*n&&pos%3==2)||(pos>=3*n+6&&(pos-3*n-6)%2==1));
 wire[10:0] a_wa=state==1?k:pi,b_wa=state==1?k:inv;
 wire signed[11:0] prior_wdata=state==1?12'sd0:clip((ext_s*3)>>>2);
 integer j;
 always @(posedge clk)begin
  if(sys_we)sys[sys_wa]<=in_llr;
  if(pa_we)pa[pa_wa]<=in_llr;
  if(pb_we)pb[pb_wa]<=in_llr;
  if(input_accept&&pos>=3*n+6&&(pos-3*n-6)%2==0)tailb[(pos-3*n-6)/2]<=in_llr;
  if(state==1||(state==19&&k<n&&half))prior_a[a_wa]<=prior_wdata;
  if(state==1||(state==19&&k<n&&!half))prior_b[b_wa]<=prior_wdata;
  if(state==4)alpha_ram[k]<=alpha_word;
  if(state==6)alpha_row<=alpha_ram[k];
  if(state==19&&k<n&&half)conv_soft[pi]<=clip(app_s);
  if(state==4)for(j=0;j<8;j=j+1)fa_s[j]<=fa[j];
  if(state==7)for(j=0;j<8;j=j+1)begin bb_s[j]<=bb[j];m0_s[j]<=m0s[j];m1_s[j]<=m1s[j];end
  if(state==10)trace_ram[k]<=picks;
  if(state==11)trace_row<=trace_ram[k];
  if(state==12&&k<length)decoded[ext]<=traceback_state[5];
 end
 always @(posedge clk)begin
  if(!rst_n)begin state<=0;pos<=0;k<=0;half<=0;iteration<=0;sy<=0;pr<=0;ap<=0;vs0<=0;vs1<=0;traceback_state<=0;scr<=511;out_index<=0;out_valid<=0;out_bit<=0;out_sop<=0;out_eop<=0;busy<=0;decode_cycles<=0;iterations_done<=0;
   for(j=0;j<8;j=j+1)begin alpha[j]<=NEG;beta[j]<=NEG;end
   for(j=0;j<64;j=j+1)vm[j]<=-4000000;
  end else if(clear)begin state<=0;pos<=0;k<=0;half<=0;iteration<=0;scr<=511;out_index<=0;out_valid<=0;busy<=0;decode_cycles<=0;iterations_done<=0;end
  else begin
   if(out_valid&&out_ready)out_valid<=0;
   if(busy)decode_cycles<=decode_cycles+1;
   case(state)
    0:if(in_valid&&in_ready)begin
     if(!fec_enable)begin out_valid<=1;out_bit<=in_llr[7];out_sop<=pos==0;out_eop<=pos==length-1;pos<=pos+1;end
     else if(pos==total-1)begin state<=1;k<=0;busy<=1;end else pos<=pos+1;
    end
    1:begin if(k==n-1)begin k<=0;state<=2;end else k<=k+1;end
    2:begin for(j=0;j<8;j=j+1)alpha[j]<=j==0?0:NEG;k<=0;state<=3;end
    3:begin
     sy<=half?(k<n?sys[pi]:tailb[k-n]):sys[k];pr<=half?pb[k]:pa[k];ap<=k<n?(half?prior_b[k]:prior_a[k]):0;state<=4;
    end
    4:state<=15;
    15:begin
     for(j=0;j<8;j=j+1)alpha[j]<=fa_s[j]<=NEG?NEG:fa_s[j]-fmax_s;
     if(k==n+2)begin for(j=0;j<8;j=j+1)beta[j]<=j==0?0:NEG;state<=6;end else begin k<=k+1;state<=3;end
    end
    6:begin sy<=half?(k<n?sys[pi]:tailb[k-n]):sys[k];pr<=half?pb[k]:pa[k];ap<=k<n?(half?prior_b[k]:prior_a[k]):0;state<=7;end
    7:state<=16;
    16:begin m0_max<=zero_max;m1_max<=one_max;for(j=0;j<8;j=j+1)beta[j]<=bb_s[j]<=NEG?NEG:bb_s[j]-bmax_s;state<=17;end
    17:begin app_s<=(m0_max-m1_max)>>>1;ext_s<=((m0_max-m1_max)>>>1)-$signed(sy)-$signed(ap);state<=19;end
    18:begin ext_s<=app_s-$signed(sy)-$signed(ap);state<=19;end
    19:begin
     if(k!=0)begin k<=k-1;state<=6;end
     else if(!half)begin half<=1;state<=2;end
     else if(!iteration)begin half<=0;iteration<=1;iterations_done<=1;state<=2;end
     else begin iterations_done<=2;state<=8;end
    end
    8:begin for(j=0;j<64;j=j+1)vm[j]<=j==0?0:-4000000;k<=0;state<=9;end
    9:begin vs0<=conv_soft[2*k];vs1<=conv_soft[2*k+1];state<=10;end
    10:begin
     for(j=0;j<64;j=j+1)vm[j]<=va[j];
     if(k==length+5)begin traceback_state<=0;state<=11;end else begin k<=k+1;state<=9;end
    end
    11:state<=12;
    12:begin traceback_state<={traceback_state[4:0],trace_row[traceback_state]};if(k==0)begin state<=13;out_index<=0;scr<=511;end else begin k<=k-1;state<=11;end end
    13:if(!out_valid||out_ready)begin
     out_valid<=1;out_bit<=decoded[out_index]^scr[0];out_sop<=out_index==0;out_eop<=out_index==length-1;scr<={scr[0]^scr[5],scr[8:1]};
     if(out_index==length-1)begin state<=14;busy<=0;end else out_index<=out_index+1;
    end
    default:begin end
   endcase
  end
 end
endmodule
