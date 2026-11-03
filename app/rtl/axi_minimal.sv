// Step13 PIO payload endpoint. AXI control is independent of the data engine.
// All software validation errors return AXI OKAY + LAST_ERROR (avoid ARM aborts).
module axi_minimal(
 input wire aclk,aresetn,
 input wire [11:0] s_axi_awaddr,input wire s_axi_awvalid,output wire s_axi_awready,
 input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,input wire s_axi_wvalid,output wire s_axi_wready,
 output reg [1:0] s_axi_bresp,output reg s_axi_bvalid,input wire s_axi_bready,
 input wire [11:0] s_axi_araddr,input wire s_axi_arvalid,output wire s_axi_arready,
 output reg [31:0] s_axi_rdata,output reg [1:0] s_axi_rresp,output reg s_axi_rvalid,input wire s_axi_rready,
 input wire accept_enable
);
 localparam ERR_BUSY=1,ERR_PENDING=2,ERR_LENGTH=3,ERR_INCOMPLETE=4,ERR_HEADER=5,ERR_COMMAND=6,ERR_READONLY=7,ERR_ADDRESS=8,ERR_NORESULT=9,ERR_RANGE=10;
 localparam RES_OK=0,RES_CRC=1,RES_FORMAT=2,RES_ABORT=3,RES_TIMEOUT=4;
 reg [7:0] tx_mem[0:95],rx_mem[0:95];reg [95:0] written;
 reg [31:0] tx_len,tag,flags,timeout_cycles,gain,sigma,hold_rx;
 reg [31:0] start_delay,channel_phase,noise_seed,channel_step,suppress;
 reg [31:0] geometric_delay,frame_class,echo_gain,echo_delay,echo_phase,echo_step,gain_delta,echo_gain_delta;
 reg [3:0] channel_taps;
 reg [31:0] tap_gain[0:7],tap_delay[0:7],tap_phase[0:7],tap_step[0:7],tap_ramp[0:7];
 wire[127:0] tap_gain_bus;wire[79:0]tap_delay_bus;wire[255:0]tap_phase_bus,tap_step_bus,tap_ramp_bus;
 genvar ti;generate for(ti=0;ti<8;ti=ti+1)begin: tap_bus
  assign tap_gain_bus[ti*16+:16]=tap_gain[ti][15:0];assign tap_delay_bus[ti*10+:10]=tap_delay[ti][9:0];
  assign tap_phase_bus[ti*32+:32]=tap_phase[ti];assign tap_step_bus[ti*32+:32]=tap_step[ti];assign tap_ramp_bus[ti*32+:32]=tap_ramp[ti];
 end endgenerate
 wire [31:0] final_rng,final_phase,final_echo_phase,clipping,training_count;
 wire signed [31:0] training_i,training_q;wire [63:0] training_energy;
 reg [31:0] bit_errors;reg [9:0] monitor_index;
 reg[31:0]fec_mode,trace_address,trace_bank,pre_errors,pre_count,evm_count;
 reg[63:0]evm_sum;reg expected_sign;
 wire enc_valid,enc_bit,enc_ready,prepared,reference_bit,demod_valid,demod_ready,diag_valid;
 wire signed[7:0]demod_llr;wire[12:0]coded_length,diag_index;
 wire signed[31:0]cfo_estimate,estimated_i,estimated_q,timing_omega;
 wire[31:0]timing_updates,decode_cycles,trace_data,trace_count,wave_origin;wire[2:0]iterations;
 wire signed[15:0]eq_i,eq_q,raw_i,raw_q;
 wire signed[31:0]evm_error=$signed(eq_i)-((expected_sign^reference_bit)?-32'sd8192:32'sd8192);
 reg signed[31:0]evm_error_reg;reg signed[15:0]evm_q_reg;reg[63:0]evm_power;reg[1:0]evm_valid;
 wire window_done;wire [31:0] captures,rx_samples,sync_errors;
 reg busy,done,rx_valid,crc_good,aborted,launch,reset_pulse;
 reg [31:0] result_code,rx_len,rx_frame_bytes,cycles,generation,last_error,result_tag;
 reg [15:0] result_calc_crc,result_recv_crc;
 reg aw_pending,w_pending;reg [11:0] awaddr;reg [31:0] wdata;reg [3:0] wstrb;
 assign s_axi_awready=!aw_pending&&!s_axi_bvalid;assign s_axi_wready=!w_pending&&!s_axi_bvalid;assign s_axi_arready=!s_axi_rvalid;
 wire local_rstn=aresetn&&!reset_pulse;
 wire tx_v,tx_r,tx_bit,tx_sop,tx_eop,tx_busy,tx_done;
 wire rx_v,rx_r,rx_bit,rx_sop,rx_eop,rx_write,rx_done,rx_crc_good,rx_format_good;
 wire [6:0] tx_index,rx_index;wire [7:0] rx_byte;
 wire [15:0] declared_len,calc_crc,recv_crc;
 wire [31:0] tx_bits,rx_bits;
 reg [31:0] tx_source,modem_profile;
 wire [7:0] hn9_byte,hn13_byte,hn9_ack,hn13_ack;
 wire hn9_ready,hn13_ready,hn9_ack_ready,hn13_ack_ready;
 wire [31:0] hn9_read,hn13_read,hn9_len,hn13_len,hn9_seq,hn13_seq;
 wire hn_write=aw_pending&&w_pending&&!s_axi_bvalid;
 hardware_node #(.NODE_ID(9)) node9(.clk(aclk),.rst_n(aresetn),
  .bus_write(hn_write&&awaddr>=12'h400&&awaddr<12'h800),.bus_addr(awaddr[9:0]),.bus_data(wdata),.bus_strb(wstrb),.read_addr(s_axi_araddr[9:0]),.read_data(hn9_read),
  .phy_busy(busy),.phy_launch(launch),.rx_write(rx_write&&busy),.rx_index(rx_index),.rx_byte(rx_byte),
  .rx_commit(rx_done&&busy),.rx_good(rx_crc_good&&rx_format_good),.rx_ack(frame_class[0]),
  .tx_index(tx_index),.tx_byte(hn9_byte),.ack_byte(hn9_ack),.tx_ready(hn9_ready),.tx_length(hn9_len),.tx_sequence(hn9_seq),.ack_ready(hn9_ack_ready));
 hardware_node #(.NODE_ID(13)) node13(.clk(aclk),.rst_n(aresetn),
  .bus_write(hn_write&&awaddr>=12'h800&&awaddr<12'hc00),.bus_addr(awaddr[9:0]),.bus_data(wdata),.bus_strb(wstrb),.read_addr(s_axi_araddr[9:0]),.read_data(hn13_read),
  .phy_busy(busy),.phy_launch(launch),.rx_write(rx_write&&busy),.rx_index(rx_index),.rx_byte(rx_byte),
  .rx_commit(rx_done&&busy),.rx_good(rx_crc_good&&rx_format_good),.rx_ack(frame_class[0]),
  .tx_index(tx_index),.tx_byte(hn13_byte),.ack_byte(hn13_ack),.tx_ready(hn13_ready),.tx_length(hn13_len),.tx_sequence(hn13_seq),.ack_ready(hn13_ack_ready));
 wire [7:0] tx_input_byte=tx_source==1?hn9_byte:tx_source==2?hn13_byte:tx_source==3?hn9_ack:tx_source==4?hn13_ack:tx_mem[tx_index];
 wire selected_ready=tx_source==1?hn9_ready:tx_source==2?hn13_ready:tx_source==3?hn9_ack_ready:tx_source==4?hn13_ack_ready:1'b0;
 wire [31:0] selected_len=tx_source==1?hn9_len:tx_source==2?hn13_len:32'd12;
 payload_tx tx(.clk(aclk),.rst_n(local_rstn),.start(launch),.ack_frame(frame_class[0]),.corrupt_crc(flags[0]),.read_index(tx_index),.read_byte(tx_input_byte),.valid(tx_v),.ready(tx_r),.data_bit(tx_bit),.sop(tx_sop),.eop(tx_eop),.busy(tx_busy),.done(tx_done),.bits_sent(tx_bits));
 fec_encoder encoder(.clk(aclk),.rst_n(local_rstn),.clear(launch),.ack_frame(frame_class[0]),.fec_enable(fec_mode[0]),.in_valid(tx_v),.in_bit(tx_bit),.in_ready(tx_r),.out_valid(enc_valid),.out_bit(enc_bit),.out_ready(enc_ready),.prepared(prepared),.coded_length(coded_length),.monitor_addr(diag_index),.monitor_bit(reference_bit));
 fec_decoder decoder(.clk(aclk),.rst_n(local_rstn),.clear(launch),.ack_frame(frame_class[0]),.fec_enable(fec_mode[0]),.in_valid(demod_valid),.in_llr(demod_llr),.in_ready(demod_ready),.out_valid(rx_v),.out_bit(rx_bit),.out_sop(rx_sop),.out_eop(rx_eop),.out_ready(rx_r),.busy(),.decode_cycles(decode_cycles),.iterations_done(iterations));
 // tx_sop/tx_eop are intentionally NOT connected to any receiver input.
 two_path_link channel(.hard_profile(modem_profile[0]),.clk(aclk),.rst_n(local_rstn),.clear(launch),.enable(busy&&prepared),.accept_enable(accept_enable&&!hold_rx[0]),.ack_frame(frame_class[0]),.fec_enable(fec_mode[0]),
  .tap_count(channel_taps),.tap_gains(tap_gain_bus),.tap_delays(tap_delay_bus),.tap_phases(tap_phase_bus),.tap_steps(tap_step_bus),.tap_ramps(tap_ramp_bus),
  .gain_q15(gain[15:0]),.sigma(sigma[15:0]),.start_delay(start_delay[10:0]),.initial_phase(channel_phase),.phase_step(channel_step),.seed(noise_seed),.suppress(suppress[0]),
  .geometric_delay(geometric_delay[9:0]),.echo_gain(echo_gain[15:0]),.echo_delay(echo_delay[5:0]),.echo_phase(echo_phase),.echo_step(echo_step),.gain_delta(gain_delta),.echo_gain_delta(echo_gain_delta),
  .final_rng(final_rng),.final_phase(final_phase),.final_echo_phase(final_echo_phase),.clipping(clipping),.training_i(training_i),.training_q(training_q),.training_energy(training_energy),.training_count(training_count),
  .tx_valid(enc_valid),.tx_bit(enc_bit),.tx_ready(enc_ready),.rx_valid(demod_valid),.rx_llr(demod_llr),.rx_ready(demod_ready),.window_done(window_done),.captures(captures),.rx_samples(rx_samples),.sync_errors(sync_errors),
  .cfo_estimate(cfo_estimate),.channel_i(estimated_i),.channel_q(estimated_q),.timing_omega(timing_omega),.timing_updates(timing_updates),.bit_index(diag_index),.eq_i(eq_i),.eq_q(eq_q),.raw_i(raw_i),.raw_q(raw_q),.diagnostic_valid(diag_valid),.trace_addr(trace_address[14:0]),.trace_equalized(trace_bank[1:0]),.trace_data(trace_data),.trace_count(trace_count),.wave_origin(wave_origin));
 payload_rx rx(.clk(aclk),.rst_n(local_rstn),.clear(launch),.ack_frame(frame_class[0]),.valid(rx_v),.ready(rx_r),.data_bit(rx_bit),.sop(rx_sop),.eop(rx_eop),.accept_enable(accept_enable&&!hold_rx[0]),
  .write_enable(rx_write),.write_index(rx_index),.write_byte(rx_byte),.done(rx_done),.crc_ok(rx_crc_good),.format_ok(rx_format_good),.payload_length(declared_len),.calculated_crc(calc_crc),.received_crc(recv_crc),.bits_received(rx_bits));
 function automatic [31:0] merge(input [31:0] oldv,newv,input [3:0] strb);integer k;begin merge=oldv;for(k=0;k<4;k=k+1)if(strb[k])merge[k*8+:8]=newv[k*8+:8];end endfunction
 wire [31:0] status={24'd0,(&written),(last_error!=0),(done&&!rx_valid),aborted,crc_good,rx_valid,done,busy};
 reg [31:0] merged;integer k,j;
 // Reference monitor is separate from receiver control/data. Compare frame-body
 // bits only; no original byte is supplied to the demodulator or RX buffer.
 wire [9:0] monitor_body_bits=frame_class[0]?10'd96:10'd768;
 // Dedicated diagnostic copy of the selected body; never connected to RX.
 reg [7:0] monitor_body[0:95];
 wire monitor_expected=monitor_index<monitor_body_bits?monitor_body[monitor_index[9:3]][7-monitor_index[2:0]]:1'b0;
 always @(posedge aclk)if(tx_v&&tx_r&&tx_index<96)monitor_body[tx_index]<=tx_input_byte;
 always @(posedge aclk)begin
  if(!aresetn)begin pre_errors<=0;pre_count<=0;evm_sum<=0;evm_count<=0;expected_sign<=0;evm_valid<=0;evm_error_reg<=0;evm_q_reg<=0;evm_power<=0;end
  else if(launch)begin pre_errors<=0;pre_count<=0;evm_sum<=0;evm_count<=0;expected_sign<=0;evm_valid<=0;evm_error_reg<=0;evm_q_reg<=0;evm_power<=0;end
  else begin
   if(demod_valid&&demod_ready)begin pre_count<=pre_count+1;if(demod_llr[7]!=reference_bit)pre_errors<=pre_errors+1;end
   evm_valid<={evm_valid[0],diag_valid};
   if(diag_valid)begin evm_error_reg<=evm_error;evm_q_reg<=eq_q;expected_sign<=expected_sign^reference_bit;end
   if(evm_valid[0])evm_power<=$signed(evm_error_reg)*$signed(evm_error_reg)+$signed(evm_q_reg)*$signed(evm_q_reg);
   if(evm_valid[1])begin evm_sum<=evm_sum+evm_power;evm_count<=evm_count+1;end
  end
 end
 always @(posedge aclk)begin
  if(!aresetn)begin bit_errors<=0;monitor_index<=0;end
  else if(launch)begin bit_errors<=0;monitor_index<=0;end
  else if(rx_v&&rx_r&&busy)begin
   if(monitor_index<monitor_body_bits&&rx_bit!=monitor_expected)bit_errors<=bit_errors+1;
   monitor_index<=monitor_index+1;
  end
 end
 always @(posedge aclk)begin
  if(!aresetn)begin
   for(k=0;k<96;k=k+1)begin tx_mem[k]<=0;rx_mem[k]<=0;end
   channel_taps<=0;
   for(k=0;k<8;k=k+1)begin tap_gain[k]<=0;tap_delay[k]<=0;tap_phase[k]<=0;tap_step[k]<=0;tap_ramp[k]<=0;end
   written<=0;tx_len<=0;tag<=0;flags<=0;timeout_cycles<=5000000;gain<=32768;sigma<=0;hold_rx<=0;
   start_delay<=0;channel_phase<=0;noise_seed<=1;channel_step<=0;suppress<=0;
   geometric_delay<=0;frame_class<=0;echo_gain<=0;echo_delay<=0;echo_phase<=0;echo_step<=0;gain_delta<=0;echo_gain_delta<=0;fec_mode<=0;trace_address<=0;trace_bank<=0;
   busy<=0;done<=0;rx_valid<=0;crc_good<=0;aborted<=0;launch<=0;reset_pulse<=0;result_code<=0;rx_len<=0;rx_frame_bytes<=0;cycles<=0;generation<=0;last_error<=0;result_tag<=0;result_calc_crc<=0;result_recv_crc<=0;tx_source<=0;modem_profile<=0;
   aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;s_axi_bresp<=0;s_axi_bvalid<=0;s_axi_rresp<=0;s_axi_rvalid<=0;s_axi_rdata<=0;
  end else begin
   launch<=0;reset_pulse<=0;
   if(busy&&!launch)begin
    cycles<=cycles+1;
    if(rx_write&&rx_index<96)rx_mem[rx_index]<=rx_byte;
    if(rx_done)begin
     busy<=0;done<=1;crc_good<=rx_crc_good;result_calc_crc<=calc_crc;result_recv_crc<=recv_crc;
     if(rx_crc_good&&rx_format_good)begin rx_valid<=1;rx_len<=declared_len;rx_frame_bytes<=frame_class[0]?12:96;result_code<=RES_OK;end
     else begin rx_valid<=0;rx_len<=0;rx_frame_bytes<=0;result_code<=rx_crc_good?RES_FORMAT:RES_CRC;end
    end else if(window_done)begin busy<=0;done<=1;rx_valid<=0;crc_good<=0;rx_len<=0;rx_frame_bytes<=0;result_code<=sync_errors!=0?6:5;end
    else if(cycles>=timeout_cycles-1)begin busy<=0;done<=1;rx_valid<=0;crc_good<=0;rx_len<=0;rx_frame_bytes<=0;result_code<=RES_TIMEOUT;reset_pulse<=1;end
   end
   if(s_axi_awvalid&&s_axi_awready)begin aw_pending<=1;awaddr<=s_axi_awaddr;end
   if(s_axi_wvalid&&s_axi_wready)begin w_pending<=1;wdata<=s_axi_wdata;wstrb<=s_axi_wstrb;end
   if(s_axi_bvalid&&s_axi_bready)s_axi_bvalid<=0;
   if(aw_pending&&w_pending&&!s_axi_bvalid)begin
    aw_pending<=0;w_pending<=0;s_axi_bvalid<=1;s_axi_bresp<=0;
    if(wstrb==0)begin end
    else if(awaddr[1:0]!=0)last_error<=ERR_ADDRESS;
    else if(awaddr==0)begin
     merged=merge(0,wdata,wstrb);
     case(merged)
      0:begin end
      16:last_error<=0;
      8:begin busy<=0;done<=1;rx_valid<=0;crc_good<=0;aborted<=1;result_code<=RES_ABORT;rx_len<=0;rx_frame_bytes<=0;written<=0;reset_pulse<=1;last_error<=0;result_calc_crc<=0;result_recv_crc<=0;end
      4:if(busy)last_error<=ERR_BUSY;else begin done<=0;rx_valid<=0;crc_good<=0;aborted<=0;result_code<=0;rx_len<=0;rx_frame_bytes<=0;written<=0;last_error<=0;hold_rx<=0;result_calc_crc<=0;result_recv_crc<=0;end
      1:begin
       if(busy)last_error<=ERR_BUSY;
       else if(done)last_error<=ERR_PENDING;
       else if(tx_len<1||tx_len>64)last_error<=ERR_LENGTH;
       else if(tx_source!=0&&(!selected_ready||selected_len!=tx_len||(frame_class[0]!=(tx_source>=3))))last_error<=ERR_HEADER;
       else if(tx_source==0&&!(&written))last_error<=ERR_INCOMPLETE;
       else if(tx_source==0&&!frame_class[0]&&(tx_mem[0]!=1||{tx_mem[29],tx_mem[28]}!=tx_len))last_error<=ERR_HEADER;
       else begin busy<=1;done<=0;rx_valid<=0;crc_good<=0;aborted<=0;result_code<=0;rx_len<=0;rx_frame_bytes<=0;cycles<=0;generation<=generation+1;result_tag<=tag;last_error<=0;result_calc_crc<=0;result_recv_crc<=0;launch<=1;end
      end
      default:last_error<=ERR_COMMAND;
     endcase
    end else if(awaddr>=12'h400&&awaddr<12'hc00)begin end // endpoint has its own error register
    else if(awaddr==12'h048)begin merged=merge(hold_rx,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else hold_rx<=merged;end
    else if(awaddr==12'h0f4)begin merged=merge(trace_address,wdata,wstrb);if(merged>32767)last_error<=ERR_RANGE;else trace_address<=merged;end
    else if(awaddr==12'h0f8)begin merged=merge(trace_bank,wdata,wstrb);if(merged>2)last_error<=ERR_RANGE;else trace_bank<=merged;end
    else if(busy)last_error<=ERR_BUSY;
    else if(done)last_error<=ERR_PENDING;
    else if(awaddr>=12'h100&&awaddr<12'h160)begin
     for(j=0;j<4;j=j+1)if(wstrb[j])begin tx_mem[awaddr-12'h100+j]<=wdata[j*8+:8];written[awaddr-12'h100+j]<=1;end
    end else if(awaddr>=12'hc00&&awaddr<12'hd00)begin
     case(awaddr[4:2])
      0:begin merged=merge(tap_gain[awaddr[7:5]],wdata,wstrb);if(merged>32768)last_error<=ERR_RANGE;else tap_gain[awaddr[7:5]]<=merged;end
      1:begin merged=merge(tap_delay[awaddr[7:5]],wdata,wstrb);if(merged>1023)last_error<=ERR_RANGE;else tap_delay[awaddr[7:5]]<=merged;end
      2:tap_phase[awaddr[7:5]]<=merge(tap_phase[awaddr[7:5]],wdata,wstrb);
      3:tap_step[awaddr[7:5]]<=merge(tap_step[awaddr[7:5]],wdata,wstrb);
      4:tap_ramp[awaddr[7:5]]<=merge(tap_ramp[awaddr[7:5]],wdata,wstrb);
      default:last_error<=ERR_ADDRESS;
     endcase
    end else begin
     case(awaddr)
      12'h004:tx_len<=merge(tx_len,wdata,wstrb);
      12'h008:tag<=merge(tag,wdata,wstrb);
      12'h00c:begin merged=merge(flags,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else flags<=merged;end
      12'h030:begin merged=merge(timeout_cycles,wdata,wstrb);if(merged<1||merged>100000000)last_error<=ERR_RANGE;else timeout_cycles<=merged;end
      12'h040:begin merged=merge(gain,wdata,wstrb);if(merged>32768)last_error<=ERR_RANGE;else gain<=merged;end
      12'h044:begin merged=merge(sigma,wdata,wstrb);if(merged>65535)last_error<=ERR_RANGE;else sigma<=merged;end
      12'h050:begin merged=merge(start_delay,wdata,wstrb);if(merged>1023)last_error<=ERR_RANGE;else start_delay<=merged;end
      12'h054:channel_phase<=merge(channel_phase,wdata,wstrb);
      12'h058:begin merged=merge(noise_seed,wdata,wstrb);if(merged==0)last_error<=ERR_RANGE;else noise_seed<=merged;end
      12'h05c:channel_step<=merge(channel_step,wdata,wstrb);
      12'h060:begin merged=merge(suppress,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else suppress<=merged;end
      12'h070:begin merged=merge(geometric_delay,wdata,wstrb);if(merged>512)last_error<=ERR_RANGE;else geometric_delay<=merged;end
      12'h074:begin merged=merge(frame_class,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else frame_class<=merged;end
      12'h078:begin merged=merge(echo_gain,wdata,wstrb);if(merged>32768)last_error<=ERR_RANGE;else echo_gain<=merged;end
      12'h07c:begin merged=merge(echo_delay,wdata,wstrb);if(merged>32)last_error<=ERR_RANGE;else echo_delay<=merged;end
      12'h080:echo_phase<=merge(echo_phase,wdata,wstrb);
      12'h084:echo_step<=merge(echo_step,wdata,wstrb);
      12'h088:gain_delta<=merge(gain_delta,wdata,wstrb);
      12'h08c:echo_gain_delta<=merge(echo_gain_delta,wdata,wstrb);
      12'h0c0:begin merged=merge(fec_mode,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else fec_mode<=merged;end
      12'h31c:begin merged=merge({28'd0,channel_taps},wdata,wstrb);if(merged>8)last_error<=ERR_RANGE;else channel_taps<=merged[3:0];end
      12'h308:begin merged=merge(modem_profile,wdata,wstrb);if(merged>1)last_error<=ERR_RANGE;else modem_profile<=merged;end
      12'h304:begin merged=merge(tx_source,wdata,wstrb);if(merged>4)last_error<=ERR_RANGE;else tx_source<=merged;end
      default:last_error<=((awaddr>=12'h200&&awaddr<12'h260)||(awaddr>=12'h010&&awaddr<=12'h04c))?ERR_READONLY:ERR_ADDRESS;
     endcase
    end
   end
   if(s_axi_rvalid&&s_axi_rready)s_axi_rvalid<=0;
   if(s_axi_arvalid&&s_axi_arready)begin
    s_axi_rvalid<=1;s_axi_rresp<=0;s_axi_rdata<=0;
    if(s_axi_araddr[1:0]!=0)last_error<=ERR_ADDRESS;
    else if(s_axi_araddr>=12'h400&&s_axi_araddr<12'h800)s_axi_rdata<=hn9_read;
    else if(s_axi_araddr>=12'h800&&s_axi_araddr<12'hc00)s_axi_rdata<=hn13_read;
    else if(s_axi_araddr>=12'h100&&s_axi_araddr<12'h160)begin
     for(j=0;j<4;j=j+1)s_axi_rdata[j*8+:8]<=tx_mem[s_axi_araddr-12'h100+j];
    end else if(s_axi_araddr>=12'h200&&s_axi_araddr<12'h260)begin
     if(rx_valid)begin for(j=0;j<4;j=j+1)s_axi_rdata[j*8+:8]<=(s_axi_araddr-12'h200+j)<rx_frame_bytes?rx_mem[s_axi_araddr-12'h200+j]:8'd0;end
     else last_error<=ERR_NORESULT;
    end else if(s_axi_araddr>=12'hc00&&s_axi_araddr<12'hd00)begin
     case(s_axi_araddr[4:2])
      0:s_axi_rdata<=tap_gain[s_axi_araddr[7:5]];
      1:s_axi_rdata<=tap_delay[s_axi_araddr[7:5]];
      2:s_axi_rdata<=tap_phase[s_axi_araddr[7:5]];
      3:s_axi_rdata<=tap_step[s_axi_araddr[7:5]];
      4:s_axi_rdata<=tap_ramp[s_axi_araddr[7:5]];
      default:last_error<=ERR_ADDRESS;
     endcase
    end else case(s_axi_araddr)
     12'h000:s_axi_rdata<=0;12'h004:s_axi_rdata<=tx_len;12'h008:s_axi_rdata<=tag;12'h00c:s_axi_rdata<=flags;
     12'h010:s_axi_rdata<=status;12'h014:s_axi_rdata<=result_code;12'h018:s_axi_rdata<=rx_len;12'h01c:s_axi_rdata<=rx_frame_bytes;
     12'h020:s_axi_rdata<=tx_bits;12'h024:s_axi_rdata<=rx_bits;12'h028:s_axi_rdata<=cycles;12'h02c:s_axi_rdata<=generation;
     12'h030:s_axi_rdata<=timeout_cycles;12'h034:s_axi_rdata<=last_error;12'h038:s_axi_rdata<=result_tag;12'h03c:s_axi_rdata<=32'h000d0005;
     12'h040:s_axi_rdata<=gain;12'h044:s_axi_rdata<=sigma;12'h048:s_axi_rdata<=hold_rx;12'h04c:s_axi_rdata<={result_recv_crc,result_calc_crc};
     12'h050:s_axi_rdata<=start_delay;12'h054:s_axi_rdata<=channel_phase;12'h058:s_axi_rdata<=noise_seed;12'h05c:s_axi_rdata<=channel_step;12'h060:s_axi_rdata<=suppress;
     12'h064:s_axi_rdata<=captures;12'h068:s_axi_rdata<=rx_samples;12'h06c:s_axi_rdata<=sync_errors;
     12'h070:s_axi_rdata<=geometric_delay;12'h074:s_axi_rdata<=frame_class;12'h078:s_axi_rdata<=echo_gain;12'h07c:s_axi_rdata<=echo_delay;
     12'h080:s_axi_rdata<=echo_phase;12'h084:s_axi_rdata<=echo_step;12'h088:s_axi_rdata<=gain_delta;12'h08c:s_axi_rdata<=echo_gain_delta;
     12'h090:s_axi_rdata<=final_rng;12'h094:s_axi_rdata<=final_phase;12'h098:s_axi_rdata<=final_echo_phase;12'h09c:s_axi_rdata<=clipping;
     12'h0a0:s_axi_rdata<=bit_errors;12'h0a4:s_axi_rdata<=monitor_index<monitor_body_bits?monitor_index:monitor_body_bits;
     12'h0a8:s_axi_rdata<=training_i;12'h0ac:s_axi_rdata<=training_q;12'h0b0:s_axi_rdata<=training_energy[31:0];12'h0b4:s_axi_rdata<=training_energy[63:32];12'h0b8:s_axi_rdata<=training_count;
     12'h0c0:s_axi_rdata<=fec_mode;12'h0c4:s_axi_rdata<=cfo_estimate;12'h0c8:s_axi_rdata<=estimated_i;12'h0cc:s_axi_rdata<=estimated_q;
     12'h0d0:s_axi_rdata<=timing_omega;12'h0d4:s_axi_rdata<=timing_updates;12'h0d8:s_axi_rdata<=pre_errors;12'h0dc:s_axi_rdata<=pre_count;
     12'h0e0:s_axi_rdata<=decode_cycles;12'h0e4:s_axi_rdata<={29'd0,iterations};12'h0e8:s_axi_rdata<=evm_sum[31:0];12'h0ec:s_axi_rdata<=evm_sum[63:32];12'h0f0:s_axi_rdata<=evm_count;
     12'h0f4:s_axi_rdata<=trace_address;12'h0f8:s_axi_rdata<=trace_bank;12'h0fc:s_axi_rdata<=trace_data;12'h300:s_axi_rdata<=trace_count;
     12'h304:s_axi_rdata<=tx_source;
     12'h308:s_axi_rdata<=modem_profile;
     12'h310:s_axi_rdata<=rx_samples;
     12'h314:s_axi_rdata<=wave_origin;
     12'h31c:s_axi_rdata<={28'd0,channel_taps};
     12'h318:s_axi_rdata<=32'h57415631; // WAV1 continuous sample readout capability
     default:last_error<=ERR_ADDRESS;
    endcase
   end
  end
 end
endmodule
