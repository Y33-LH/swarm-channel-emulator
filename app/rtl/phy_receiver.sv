// Buffered sample-domain receiver, rectangular 4-sample symbols.
// Acquisition sees only channel IQ. Pilot-derived CFO and complex gain;
// interpolating Gardner timing loop; trained 8-tap complex decision feedback.
// No channel configuration, original payload or TX frame boundary input.
module phy_receiver(
 input wire clk,rst_n,clear,in_valid,ack_frame,fec_enable,hard_profile,
 input wire signed[15:0]in_i,in_q,output wire in_ready,
 output reg valid,output reg signed[7:0]llr,input wire ready,
 output reg failed,output wire[31:0]captures,search_samples,sync_errors,
 output wire signed[31:0]training_i,training_q,output wire[63:0]training_energy,output wire[31:0]training_count,
 output reg signed[31:0]cfo_step,channel_i,channel_q,timing_omega,
 output reg[31:0] timing_updates,output reg[12:0]bit_index,
 output reg signed[15:0]eq_i,eq_q,raw_i,raw_q,output reg diagnostic_valid,
 input wire[14:0]trace_addr,input wire[1:0]trace_equalized,output reg[31:0]trace_data,output reg[31:0]trace_count,
 output wire[31:0]wave_origin
);
 `include "preamble_constant.vh"
 reg[14:0]sample_addr;wire[31:0]sample_word,trace_raw_word,trace_eq_word;
 reg[31:0]received;reg[5:0]state;reg[31:0]target;
 wire[14:0]burst_addr=state==10?target[30:16]:state==11?target[30:16]+1:state==12?target[30:16]-2:target[30:16]-1;
 // Only the completed/failed receiver can lend its BRAM read port to the host.
 // The samples are the original consecutive channel outputs, not symbols.
 wire wave_read=(trace_equalized==2)&&((state==31)||failed);
 wire[14:0]sample_read_addr=wave_read?trace_addr:(state==10||state==11||state==12||state==25)?burst_addr:sample_addr;
 wire acquired;wire[31:0]origin,acq_count;
 assign wave_origin=origin;
 wire capture_accept=in_valid&&in_ready;
 sample_bram sample_store(.clk(clk),.we(capture_accept),.wa(received[14:0]),.ra(sample_read_addr),.d({in_q,in_i}),.q(sample_word));
 sample_bram #(.A(9)) raw_trace_store(.clk(clk),.we(diagnostic_valid&&bit_index<512),.wa(bit_index[8:0]),.ra(trace_addr[8:0]),.d({raw_q,raw_i}),.q(trace_raw_word));
 sample_bram #(.A(9)) eq_trace_store(.clk(clk),.we(diagnostic_valid&&bit_index<512),.wa(bit_index[8:0]),.ra(trace_addr[8:0]),.d({eq_q,eq_i}),.q(trace_eq_word));
 wire[12:0]body=fec_enable?(ack_frame?720:4752):(ack_frame?112:784);
 wire[31:0]search_limit=ack_frame?10000:26000;
 assign in_ready=state!=31&&!failed&&received<search_limit&&(!acquired||received<origin+4*(542+body)+64);
 assign search_samples=received;
 dbpsk_capture acquisition(.clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(capture_accept),.ack_frame(ack_frame),.in_i(in_i),.in_q(in_q),.in_ready(),.valid(),.data_bit(),.sop(),.eop(),.ready(1'b1),.captures(captures),.search_samples(acq_count),.sync_errors(sync_errors),.acquired(acquired),.frame_origin(origin),.training_i(training_i),.training_q(training_q),.training_energy(training_energy),.training_count(training_count));
 reg[6:0]pilot_k;reg signed[31:0]sum1i,sum1q,sum2i,sum2q;
 reg signed[31:0]h1i,h1q,h2i,h2q;
 reg signed[15:0]repeat_i,repeat_q;reg signed[31:0]fine_phase,fine_step;
 reg signed[63:0]cross_i,cross_q;reg atan_start;wire atan_done;wire signed[31:0]angle;
 phase_atan atan(.clk(clk),.rst_n(rst_n),.start(atan_start),.xi(cross_i),.yi(cross_q),.done(atan_done),.angle(angle));
 reg div_start;reg[63:0]numerator;reg[31:0]denominator;wire div_done;wire[63:0]quotient;
 div_u64 divide(.clk(clk),.rst_n(rst_n),.start(div_start),.numerator(numerator),.denominator(denominator),.done(div_done),.quotient(quotient));
 reg signed[31:0]coef_i,coef_q;
 reg signed[16:0]sine[0:255];initial $readmemh("sine_q15.mem",sine);
 reg[12:0]symbol;reg[31:0]rotation;
 reg[2:0]read_k;reg[31:0]points[0:3];
 reg signed[15:0]cur_i,cur_q,mid_i,mid_q,prev_i,prev_q,previous_eq_i,previous_eq_q;
 reg signed[17:0]fb_i[0:7],fb_q[0:7];reg[7:0]decisions;
 reg signed[31:0]rot_i,rot_q;reg signed[31:0]norm_i,norm_q;
 reg signed[31:0]zi,zq,error_i,error_q;
 reg signed[32:0]gardner_i,gardner_q;reg signed[33:0]gardner;
 reg signed[31:0]feedback_i_hold,feedback_q_hold,phase_hold,omega_hold;reg signed[31:0]omega_next,phase_adjust;
 reg signed[31:0]feedback_i,feedback_q;
 wire[7:0]cos_addr=rotation[31:24]+8'd64;
 wire signed[16:0]co=sine[cos_addr],si=sine[rotation[31:24]];
 wire signed[48:0]rotprod_i=$signed(cur_i)*$signed(co)+$signed(cur_q)*$signed(si);
 wire signed[48:0]rotprod_q=$signed(cur_q)*$signed(co)-$signed(cur_i)*$signed(si);
 wire signed[63:0]gainprod_i=$signed(rot_i)*$signed(coef_i)-$signed(rot_q)*$signed(coef_q);
 wire signed[63:0]gainprod_q=$signed(rot_i)*$signed(coef_q)+$signed(rot_q)*$signed(coef_i);
 wire signed[7:0] decision_metric;
 dbpsk_metric metric_extension(.hard_profile(hard_profile),.i(eq_i),.q(eq_q),.previous_i(previous_eq_i),.previous_q(previous_eq_q),.metric(decision_metric));
 wire signed[63:0]increment=$signed(cfo_step)*$signed(timing_omega);
 wire signed[63:0]elapsed_q16=$signed({1'b0,target})-($signed({1'b0,origin})+64'sd1080)*64'sd65536;
 wire signed[63:0]estimated_phase=elapsed_q16*$signed(cfo_step);
 wire signed[16:0]pi_val=preamble[254+pilot_k]?-$signed({sample_word[15],sample_word[15:0]}):$signed({sample_word[15],sample_word[15:0]});
 wire signed[16:0]pq_val=preamble[254+pilot_k]?-$signed({sample_word[31],sample_word[31:16]}):$signed({sample_word[31],sample_word[31:16]});
 function automatic signed[15:0]sat(input signed[63:0]x);begin sat=x>32767?16'sd32767:x< -32768?-16'sd32768:x[15:0];end endfunction
 function automatic signed[17:0]satfb(input signed[31:0]x);begin satfb=x>32767?18'sd32767:x< -32768?-18'sd32768:x[17:0];end endfunction
 function automatic signed[15:0]interp(input signed[15:0]a,b,input[15:0]f);reg signed[16:0]diff;reg signed[34:0]p;begin diff=$signed(b)-$signed(a);p=diff*$signed({1'b0,f});interp=$signed(a)+(p>>>16);end endfunction
 integer j;
 always @* begin
  feedback_i=0;feedback_q=0;
  for(j=0;j<8;j=j+1)begin feedback_i=feedback_i+(decisions[j]?-$signed(fb_i[j]):$signed(fb_i[j]));feedback_q=feedback_q+(decisions[j]?-$signed(fb_q[j]):$signed(fb_q[j]));end
  zi=norm_i-feedback_i_hold;zq=norm_q-feedback_q_hold;
  error_i=zi-(symbol<542?(preamble[symbol]?-8192:8192):(zi<0?-8192:8192));error_q=zq;

  // Round to nearest: arithmetic truncation biases sub-LSB negative errors
  // by -1 on weak links and eventually causes a whole-symbol slip.
  omega_next=$signed(timing_omega)+((gardner+64'sd2097152)>>>22);
  if(omega_next>262406)omega_next=262406;if(omega_next<261882)omega_next=261882;
  phase_adjust=(gardner+64'sd8192)>>>14;
  if(phase_adjust>8192)phase_adjust=8192;if(phase_adjust< -8192)phase_adjust=-8192;
 end
 always @(posedge clk)begin
  trace_data<=wave_read?sample_word:trace_equalized[0]?trace_eq_word:trace_raw_word;
 end
 always @(posedge clk)begin
  if(!rst_n)begin
   received<=0;state<=0;valid<=0;llr<=0;failed<=0;sample_addr<=0;pilot_k<=0;sum1i<=0;sum1q<=0;sum2i<=0;sum2q<=0;h1i<=0;h1q<=0;h2i<=0;h2q<=0;cross_i<=0;cross_q<=0;atan_start<=0;div_start<=0;numerator<=0;denominator<=1;coef_i<=0;coef_q<=0;cfo_step<=0;channel_i<=0;channel_q<=0;timing_omega<=262144;timing_updates<=0;bit_index<=0;eq_i<=0;eq_q<=0;raw_i<=0;raw_q<=0;diagnostic_valid<=0;trace_count<=0;target<=0;symbol<=0;rotation<=0;read_k<=0;cur_i<=0;cur_q<=0;mid_i<=0;mid_q<=0;prev_i<=0;prev_q<=0;previous_eq_i<=0;previous_eq_q<=0;rot_i<=0;rot_q<=0;norm_i<=0;norm_q<=0;decisions<=0;repeat_i<=0;repeat_q<=0;fine_phase<=0;fine_step<=0;
   for(j=0;j<8;j=j+1)begin fb_i[j]<=0;fb_q[j]<=0;end
  end else if(clear)begin
   received<=0;state<=0;valid<=0;failed<=0;pilot_k<=0;sum1i<=0;sum1q<=0;sum2i<=0;sum2q<=0;atan_start<=0;div_start<=0;cfo_step<=0;channel_i<=0;channel_q<=0;timing_omega<=262144;timing_updates<=0;bit_index<=0;diagnostic_valid<=0;trace_count<=0;decisions<=0;prev_i<=0;prev_q<=0;fine_phase<=0;fine_step<=0;
   for(j=0;j<8;j=j+1)begin fb_i[j]<=0;fb_q[j]<=0;end
  end else begin
   atan_start<=0;div_start<=0;diagnostic_valid<=0;if(valid&&ready)valid<=0;
   if(capture_accept)received<=received+1;
   case(state)
    0:begin
     if(acquired)begin state<=1;pilot_k<=0;end
     else if(received==search_limit)begin failed<=1;state<=31;end
    end
    1:begin sample_addr<=origin+4*(254+pilot_k)+2;state<=2;end
    2:state<=3;
    3:begin
     if(pilot_k<32)begin sum1i<=sum1i+pi_val;sum1q<=sum1q+pq_val;end else begin sum2i<=sum2i+pi_val;sum2q<=sum2q+pq_val;end
     if(pilot_k==63)state<=4;else begin pilot_k<=pilot_k+1;state<=1;end
    end
    4:begin h1i<=sum1i>>>5;h1q<=sum1q>>>5;h2i<=sum2i>>>5;h2q<=sum2q>>>5;channel_i<=sum1i>>>5;channel_q<=sum1q>>>5;state<=5;end
    5:begin cross_i<=0;cross_q<=0;pilot_k<=8;denominator<=$signed(h1i)*$signed(h1i)+$signed(h1q)*$signed(h1q);state<=20;end
    6:begin atan_start<=1;state<=7;end
    7:if(atan_done)begin cfo_step<=$signed(angle)/32'sd508;numerator<=(h1i<0?-$signed({{32{h1i[31]}},h1i}):$signed({{32{h1i[31]}},h1i}))<<31;div_start<=1;state<=8;end
    8:if(div_done)begin coef_i<=h1i<0?-$signed(quotient[31:0]):$signed(quotient[31:0]);numerator<=(h1q<0?-$signed({{32{h1q[31]}},h1q}):$signed({{32{h1q[31]}},h1q}))<<31;div_start<=1;state<=9;end
    9:if(div_done)begin
     coef_q<=h1q<0?$signed(quotient[31:0]):-$signed(quotient[31:0]);
     target<=((origin+1017)<<16)+32768;symbol<=254;rotation<=-$signed(cfo_step)*32'sd62;read_k<=0;state<=10;
     if(denominator<64)begin failed<=1;state<=31;end
    end
    // BRAM read bursts overlap address issue and the registered read return.
    // The sample producer runs independently; never read unwritten samples.
    10:if(target[30:16]+1<received)state<=11;
    11:begin points[0]<=sample_word;state<=12;end
    12:begin points[1]<=sample_word;state<=25;end
    25:begin points[2]<=sample_word;state<=26;end
    26:begin points[3]<=sample_word;state<=13;end
    13:begin feedback_i_hold<=feedback_i;feedback_q_hold<=feedback_q;cur_i<=interp(points[0][15:0],points[1][15:0],target[15:0]);cur_q<=interp(points[0][31:16],points[1][31:16],target[15:0]);mid_i<=interp(points[2][15:0],points[3][15:0],target[15:0]);mid_q<=interp(points[2][31:16],points[3][31:16],target[15:0]);rotation<=(estimated_phase>>>16)+$signed(fine_phase);state<=14;end
    14:begin
     gardner_i<=($signed({prev_i[15],prev_i})-$signed({cur_i[15],cur_i}))*$signed(mid_i);
     gardner_q<=($signed({prev_q[15],prev_q})-$signed({cur_q[15],cur_q}))*$signed(mid_q);
     rot_i<=rotprod_i>>>15;rot_q<=rotprod_q>>>15;state<=15;end
    15:begin gardner<=$signed({gardner_i[32],gardner_i})+$signed({gardner_q[32],gardner_q});norm_i<=gainprod_i>>>18;norm_q<=gainprod_q>>>18;state<=16;end
    16:begin
     eq_i<=sat(zi);eq_q<=sat(zq);raw_i<=cur_i;raw_q<=cur_q;
     for(j=0;j<8;j=j+1)begin
      fb_i[j]<=satfb($signed(fb_i[j])+(decisions[j]?-$signed(error_i>>> (symbol<542?5:9)):$signed(error_i>>> (symbol<542?5:9))));
      fb_q[j]<=satfb($signed(fb_q[j])+(decisions[j]?-$signed(error_q>>> (symbol<542?5:9)):$signed(error_q>>> (symbol<542?5:9))));
     end
     decisions<={decisions[6:0],symbol<542?preamble[symbol]:zi<0};
     fine_phase<=fine_phase+fine_step+((symbol<542?preamble[symbol]:zi<0)?-(error_q<<<10):(error_q<<<10));
     fine_step<=fine_step+((symbol<542?preamble[symbol]:zi<0)?-(error_q<<<1):(error_q<<<1));
     phase_hold<=phase_adjust;omega_hold<=omega_next;
     if(symbol>254)begin timing_omega<=omega_next;timing_updates<=timing_updates+1;end
     prev_i<=cur_i;prev_q<=cur_q;state<=17;
    end
    17:begin
     target<=symbol>254?target+omega_hold+phase_hold:target+262144;
     previous_eq_i<=eq_i;previous_eq_q<=eq_q;
     if(symbol>=542)begin
      llr<=decision_metric;
      valid<=1;bit_index<=symbol-542;diagnostic_valid<=1;if(symbol-542<512)trace_count<=symbol-541;state<=18;
     end else begin symbol<=symbol+1;read_k<=0;state<=10;end
    end
    18:if(valid&&ready)begin if(symbol==541+body)state<=31;else begin symbol<=symbol+1;read_k<=0;state<=10;end end
    20:begin sample_addr<=origin+4*pilot_k+2;state<=21;end
    21:state<=22;
    22:begin repeat_i<=sample_word[15:0];repeat_q<=sample_word[31:16];sample_addr<=origin+4*(pilot_k+127)+2;state<=23;end
    23:state<=24;
    24:begin
     cross_i<=cross_i+$signed(sample_word[15:0])*$signed(repeat_i)+$signed(sample_word[31:16])*$signed(repeat_q);
     cross_q<=cross_q+$signed(sample_word[31:16])*$signed(repeat_i)-$signed(sample_word[15:0])*$signed(repeat_q);
     if(pilot_k==126)state<=6;else begin pilot_k<=pilot_k+1;state<=20;end
    end
    default:begin end
   endcase
  end
 end
endmodule
