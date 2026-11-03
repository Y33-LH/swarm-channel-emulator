// Independent board-internal endpoint. ARM supplies model clock/position only.
// Business framing, bounded queue, sequence, ACK/retry and command execution
// live here. Received bytes come exclusively from the shared PHY decoder.
module hardware_node #(parameter [7:0] NODE_ID=9)(
 input wire clk,rst_n,
 input wire bus_write,input wire [9:0] bus_addr,input wire [31:0] bus_data,
 input wire [3:0] bus_strb,input wire [9:0] read_addr,output reg [31:0] read_data,
 input wire phy_busy,phy_launch,rx_write,input wire [6:0] rx_index,
 input wire [7:0] rx_byte,input wire rx_commit,rx_good,rx_ack,
 input wire [6:0] tx_index,output wire [7:0] tx_byte,ack_byte,
 output wire tx_ready,output wire [31:0] tx_length,tx_sequence,
 output wire ack_ready
);
 localparam IDLE=0,ALLOC=1,BUILD=2,SCAN=3,FETCH=4,FETCH_WAIT=5,SCAN_WAIT=6,SCAN_EVAL=7;
 reg [2:0] state;
 reg [31:0] run_id,model_round,pos_x,pos_y,pos_z,enabled,load_pps;
 reg [31:0] hb_period,next_hb,media_pause,media_rate,altitude,altitude_generation;
 reg [31:0] seq_counter,error_code,generated_hb,generated_response,generated_load;
 reg [31:0] dropped,acked,retried,expired,duplicates,executions,rejected,reset_count;
 reg [31:0] received_status,received_id,received_valid;
 reg [31:0] rx_words[0:23],tx_words[0:23],ack_words[0:2];
 reg ack_valid,selected;reg [6:0] selected_slot;
 reg [127:0] valid_slots;
 reg [7:0] occupancy;reg only_retry;
 // Queue metadata also lives in RAM. Resetting a 128-entry register bank
 // would synthesize large asynchronous read multiplexers on this device.
 (* ram_style="block" *) reg [72:0] metadata[0:127];
 reg [6:0] meta_addr,meta_write_addr;reg [72:0] meta_data,meta_write_data;
 reg meta_write;reg [31:0] best_created,selected_created;
 reg [1:0] best_priority,selected_priority;reg [6:0] best_attempt,selected_attempt_reg;
 always @(posedge clk)begin
  if(meta_write)metadata[meta_write_addr]<=meta_write_data;
  meta_data<=metadata[meta_addr];
 end
 // 128 x 96-byte queue, synchronous read, no memory reset (valid bits guard it).
 (* ram_style="block" *) reg [31:0] frames[0:4095];
 reg [11:0] mem_read_addr;reg [31:0] mem_read_data;
 reg mem_write;reg [11:0] mem_write_addr;reg [31:0] mem_write_data;
 always @(posedge clk)begin
  if(mem_write)frames[mem_write_addr]<=mem_write_data;
  mem_read_data<=frames[mem_read_addr];
 end
 reg [7:0] cursor;reg [6:0] free_slot,best_slot;reg best_valid;
 reg [4:0] word_index;reg [31:0] pending_hb,pending_load,load_accum;
 reg pending_response;reg [31:0] response_id,response_status;
 reg [31:0] command_ids[0:15],command_statuses[0:15];reg [15:0] command_valid;
 reg [4:0] command_count;reg [31:0] last_tick;reg tick_valid;
 reg [31:0] gen_type,gen_seq,gen_round,gen_x,gen_y,gen_z;
 reg [31:0] gen_id,gen_status,gen_period,gen_pause,gen_rate;
 reg [63:0] gen_time;
 reg [31:0] temp_status,temp_id,temp_value;integer i,found;
 wire [31:0] selected_attempt={25'd0,selected_attempt_reg};
 assign tx_ready=selected&&state==IDLE&&!pending_hb&&!pending_response&&!pending_load&&enabled!=0;
 assign tx_length=tx_words[7][15:0];
 assign tx_sequence=tx_words[3];
 assign tx_byte=tx_index==30?selected_attempt[7:0]:
                 tx_index<96?tx_words[tx_index[6:2]][tx_index[1:0]*8+:8]:8'd0;
 assign ack_ready=ack_valid;
 assign ack_byte=tx_index<12?ack_words[tx_index[3:2]][tx_index[1:0]*8+:8]:8'd0;
 // 96 PCM4 beacon samples at 2400 Hz. Byte zero is transmitted first.
 localparam [383:0] HB_AUDIO = NODE_ID==9 ? 384'h8898669b845be726dd627dc528eb439ea34be825cd726dd627dc528eb43aea34be825cd726dd627ec429da559b967988 : 384'h8877a956bb44cc44cd43bd53bd62ae629e729e828e827e927ea26ea35db35db34dc44cd43cd53bd53ae639c759a87888;
 function [31:0] frame_word(input [4:0] w);
  begin
   frame_word=0;
   case(w)
    0:frame_word={8'd5,8'd2,gen_type[7:0],8'd1};
    1:frame_word={NODE_ID+8'd1,NODE_ID,8'd0,NODE_ID};
    2:frame_word=run_id;
    3:frame_word=gen_seq;
    4:frame_word=32'h00010000;
    5:frame_word=gen_time[31:0];
    6:frame_word=gen_time[63:32];
    7:frame_word=gen_type==7?20:64;
    8:frame_word=gen_type==1?gen_x:gen_type==7?gen_id:gen_seq^32'h5a37c901;
    9:frame_word=gen_type==1?gen_y:gen_type==7?gen_status:gen_seq^32'ha581d032;
    10:frame_word=gen_type==1?gen_z:gen_type==7?gen_period:gen_seq^32'h1347bade;
    11:frame_word=gen_type==1?gen_round:gen_type==7?gen_pause:gen_seq^32'hfebc9821;
    12:frame_word=gen_type==1?HB_AUDIO[31:0]:gen_type==7?gen_rate:gen_type==5?gen_seq^32'hcafe2018:0;
    default:frame_word=gen_type==1?HB_AUDIO[(w-12)*32+:32]:gen_type==5?(gen_seq^{24'hdecafe,3'd0,w}):0;
   endcase
  end
 endfunction
 always @* begin
  read_data=0;
  if(read_addr>=10'h100&&read_addr<10'h160)
   read_data=selected?tx_words[read_addr[6:2]]:0;
  else if(read_addr>=10'h200&&read_addr<10'h260)
   read_data=received_valid?rx_words[read_addr[6:2]]:0;
  else case(read_addr)
   'h004:read_data=run_id;'h008:read_data=model_round;
   'h00c:read_data=pos_x;'h010:read_data=pos_y;'h014:read_data=pos_z;
   'h018:read_data=enabled;'h01c:read_data=load_pps;
   'h040:read_data={28'd0,ack_valid,selected,enabled!=0,(state!=IDLE||pending_hb!=0||pending_response||pending_load!=0)};
   'h044:read_data=generated_hb;'h048:read_data=generated_response;
   'h04c:read_data=generated_load;'h050:read_data=dropped;
   'h054:read_data=acked;'h058:read_data=retried;'h05c:read_data=expired;
   'h060:read_data=duplicates;'h064:read_data=executions;
   'h068:read_data=hb_period*100;'h06c:read_data=media_pause;
   'h070:read_data=media_rate;'h074:read_data=altitude;
   'h078:read_data=tx_length;'h07c:read_data=selected_attempt;
   'h080:read_data=tx_sequence;'h084:read_data=received_status;
   'h088:read_data=error_code;'h08c:read_data=received_id;
   'h090:read_data=altitude_generation;'h094:read_data=rejected;
   'h098:read_data=reset_count;'h09c:read_data={24'h484e01,NODE_ID};
   'h0a0:read_data={24'd0,occupancy};
   'h0a4:read_data=seq_counter;
   default:read_data=0;
  endcase
 end
 always @(posedge clk) begin
  if(!rst_n)begin
   state<=IDLE;run_id<=0;model_round<=0;pos_x<=0;pos_y<=0;pos_z<=0;enabled<=0;load_pps<=0;
   hb_period<=10;next_hb<=0;media_pause<=0;media_rate<=5;altitude<=0;altitude_generation<=0;
   seq_counter<=32'h80000000;error_code<=0;generated_hb<=0;generated_response<=0;generated_load<=0;
   dropped<=0;acked<=0;retried<=0;expired<=0;duplicates<=0;executions<=0;rejected<=0;reset_count<=0;
   received_status<=0;received_id<=0;received_valid<=0;ack_valid<=0;selected<=0;selected_slot<=0;
   valid_slots<=0;occupancy<=0;only_retry<=0;mem_read_addr<=0;mem_write<=0;mem_write_addr<=0;mem_write_data<=0;
   meta_addr<=0;meta_write_addr<=0;meta_write_data<=0;meta_write<=0;
   best_created<=0;selected_created<=0;best_priority<=0;selected_priority<=0;best_attempt<=0;selected_attempt_reg<=0;
   cursor<=0;free_slot<=0;best_slot<=0;best_valid<=0;word_index<=0;
   pending_hb<=0;pending_load<=0;load_accum<=0;pending_response<=0;response_id<=0;response_status<=0;
   command_valid<=0;command_count<=0;last_tick<=0;tick_valid<=0;
   gen_type<=0;gen_seq<=0;gen_round<=0;gen_x<=0;gen_y<=0;gen_z<=0;gen_id<=0;gen_status<=0;
   gen_period<=0;gen_pause<=0;gen_rate<=0;gen_time<=0;
   for(i=0;i<24;i=i+1)begin rx_words[i]<=0;tx_words[i]<=0;end
   for(i=0;i<3;i=i+1)ack_words[i]<=0;
   for(i=0;i<16;i=i+1)begin command_ids[i]<=0;command_statuses[i]<=0;end
  end else begin
   mem_write<=0;
   meta_write<=0;
   if(rx_write&&rx_index<96)rx_words[rx_index[6:2]][rx_index[1:0]*8+:8]<=rx_byte;
   case(state)
    IDLE:begin
     if(pending_hb||pending_response||pending_load)begin
      gen_type<=pending_hb?1:pending_response?7:5;gen_seq<=seq_counter+1;
      gen_round<=model_round;gen_time<={32'd0,model_round}*64'd100000000;
      gen_x<=pos_x;gen_y<=pos_y;gen_z<=pos_z;
      gen_id<=response_id;gen_status<=response_status;
      gen_period<=hb_period*100;gen_pause<=media_pause;gen_rate<=media_rate;
      cursor<=0;state<=ALLOC;
     end
    end
    ALLOC:begin
     if(cursor==128)begin
      dropped<=dropped+1;
      seq_counter<=gen_seq;
      if(gen_type==1)begin pending_hb<=0;generated_hb<=generated_hb+1;end
      else if(gen_type==7)begin pending_response<=0;generated_response<=generated_response+1;end
      else begin pending_load<=pending_load-1;generated_load<=generated_load+1;end
      state<=IDLE;
     end else if(!valid_slots[cursor[6:0]])begin
      free_slot<=cursor[6:0];word_index<=0;state<=BUILD;
     end else cursor<=cursor+1;
    end
    BUILD:begin
     mem_write<=1;mem_write_addr<={free_slot,word_index};mem_write_data<=frame_word(word_index);
     if(word_index==23)begin
      valid_slots[free_slot]<=1;occupancy<=occupancy+1;
      meta_write<=1;meta_write_addr<=free_slot;
      meta_write_data<={gen_type==1?2'd0:gen_type==7?2'd1:2'd2,7'd0,32'd0,gen_round};
      seq_counter<=gen_seq;state<=IDLE;
      if(gen_type==1)begin generated_hb<=generated_hb+1;pending_hb<=0;end
      else if(gen_type==7)begin generated_response<=generated_response+1;pending_response<=0;end
      else begin generated_load<=generated_load+1;pending_load<=pending_load-1;end
     end else word_index<=word_index+1;
    end
    SCAN:begin
     if(cursor==128)begin
      if(best_valid)begin selected_slot<=best_slot;selected_created<=best_created;selected_priority<=best_priority;selected_attempt_reg<=best_attempt;word_index<=0;mem_read_addr<={best_slot,5'd0};state<=FETCH_WAIT;end
      else begin selected<=0;state<=IDLE;end
     end else if(valid_slots[cursor[6:0]])begin meta_addr<=cursor[6:0];state<=SCAN_WAIT;end
     else cursor<=cursor+1;
    end
    SCAN_WAIT:state<=SCAN_EVAL;
    SCAN_EVAL:begin
     if(model_round-meta_data[31:0]>=600)begin valid_slots[cursor[6:0]]<=0;occupancy<=occupancy-1;expired<=expired+1;end
     else if((!only_retry||meta_data[70:64]!=0)&&meta_data[63:32]<=model_round&&(!best_valid||meta_data[72:71]<best_priority||
       (meta_data[72:71]==best_priority&&meta_data[31:0]<best_created)))begin
       best_valid<=1;best_slot<=cursor[6:0];best_created<=meta_data[31:0];best_priority<=meta_data[72:71];best_attempt<=meta_data[70:64];
     end
     cursor<=cursor+1;state<=SCAN;
    end
    FETCH_WAIT:state<=FETCH;
    FETCH:begin
     tx_words[word_index]<=mem_read_data;
     if(word_index==23)begin selected<=1;state<=IDLE;end
     else begin word_index<=word_index+1;mem_read_addr<={selected_slot,word_index+5'd1};state<=FETCH_WAIT;end
    end
    default:state<=IDLE;
   endcase
   // Commit only actual, CRC-checked decoder output. No software receive injection.
   if(rx_commit)begin
    received_valid<=rx_good;
    if(rx_good&&rx_ack&&selected&&rx_words[0]==run_id&&rx_words[1]==tx_sequence&&
      rx_words[2]=={8'd0,NODE_ID+8'd1,16'd0})begin
     valid_slots[selected_slot]<=0;occupancy<=occupancy-1;selected<=0;acked<=acked+1;
    end
    if(!rx_ack)begin
     received_status<=0;ack_valid<=0;
     if(rx_good&&enabled!=0&&state==IDLE&&rx_words[0][15:0]==16'h0601&&
       rx_words[1][7:0]==0&&rx_words[1][15:8]==NODE_ID&&rx_words[1][31:24]==NODE_ID&&
       rx_words[2]==run_id&&rx_words[7][15:0]==16)begin
      temp_id=rx_words[8];temp_value=rx_words[10];temp_status=2;found=-1;
      for(i=0;i<16;i=i+1)if(command_valid[i]&&command_ids[i]==temp_id)found=i;
      received_id<=temp_id;
      if(found>=0)begin duplicates<=duplicates+1;received_status<=2;ack_valid<=1;end
      else if(command_count>=16||pending_response||pending_hb||pending_load||(&valid_slots))begin received_status<=0;rejected<=rejected+1;end
      else begin
       if({32'd0,model_round}*64'd100>rx_words[11])temp_status=4;
       else case(rx_words[9][7:0])
        1:begin end
        2:if(temp_value>=100&&temp_value<=10000&&temp_value%100==0)begin hb_period<=temp_value/100;next_hb<=model_round+temp_value/100;end else temp_status=3;
        3:if(temp_value<=1)media_pause<=temp_value;else temp_status=3;
        4:if(temp_value>=1&&temp_value<=5)media_rate<=temp_value;else temp_status=3;
        5:if(temp_value>=100&&temp_value<=800&&temp_value*1000+100000>=pos_z&&temp_value*1000<=pos_z+100000)begin altitude<=temp_value;altitude_generation<=altitude_generation+1;end else temp_status=3;
        default:temp_status=3;
       endcase
       command_ids[command_count[3:0]]<=temp_id;command_statuses[command_count[3:0]]<=temp_status;
       command_valid[command_count[3:0]]<=1;command_count<=command_count+1;
       response_id<=temp_id;response_status<=temp_status;pending_response<=1;
       executions<=executions+1;received_status<=1;ack_valid<=1;
      end
      ack_words[0]<=run_id;ack_words[1]<=rx_words[3];
      ack_words[2]<={(found>=0||(command_count<16&&!pending_response&&!pending_hb&&!pending_load&&!(&valid_slots)))?8'd0:8'd1,NODE_ID,rx_words[4][15:0]};
     end
    end
   end
   if(bus_write)begin
    if(bus_strb!=15||bus_addr[1:0]!=0)error_code<=8;
    else if(phy_busy||state!=IDLE||pending_hb||pending_response||pending_load)error_code<=1;
    else case(bus_addr)
     'h000:case(bus_data)
      1:begin
       valid_slots<=0;occupancy<=0;selected<=0;pending_hb<=0;pending_response<=0;pending_load<=0;load_accum<=0;
       hb_period<=10;next_hb<=0;media_pause<=0;media_rate<=5;altitude<=0;altitude_generation<=0;
       seq_counter<=32'h80000000;error_code<=0;generated_hb<=0;generated_response<=0;generated_load<=0;
       dropped<=0;acked<=0;retried<=0;expired<=0;duplicates<=0;executions<=0;rejected<=0;
       received_status<=0;received_valid<=0;ack_valid<=0;command_valid<=0;command_count<=0;tick_valid<=0;
      end
      2:if(selected)error_code<=2;
        else if(tick_valid&&model_round<=last_tick)error_code<=10;
        else begin
         tick_valid<=1;last_tick<=model_round;
         if(enabled!=0)begin
          if(model_round>=next_hb)begin pending_hb<=1;next_hb<=model_round+hb_period;end
          if(!media_pause)begin pending_load<=(load_accum+load_pps)/10;load_accum<=(load_accum+load_pps)%10;end
         end
        end
      3,6:if(selected)error_code<=2;else if(enabled!=0)begin only_retry<=bus_data==6;state<=SCAN;cursor<=0;best_valid<=0;end
      4:if(selected)begin
         if(selected_attempt_reg>=63)begin valid_slots[selected_slot]<=0;occupancy<=occupancy-1;expired<=expired+1;end
         else begin
          meta_write<=1;meta_write_addr<=selected_slot;
          meta_write_data<={selected_priority,selected_attempt_reg+7'd1,model_round+(selected_attempt_reg<2?32'd1:32'd10),selected_created};
          retried<=retried+1;
         end
         selected<=0;
        end
      5:error_code<=0;
      16:begin valid_slots<=0;occupancy<=0;selected<=0;ack_valid<=0;reset_count<=reset_count+1;end
      default:error_code<=6;
     endcase
     'h004:run_id<=bus_data;
     'h008:model_round<=bus_data;
     'h00c:pos_x<=bus_data;'h010:pos_y<=bus_data;'h014:pos_z<=bus_data;
     'h018:if(bus_data<=1)enabled<=bus_data;else error_code<=10;
     'h01c:if(bus_data<=100)load_pps<=bus_data;else error_code<=10;
     default:error_code<=7;
    endcase
   end
  end
 end
endmodule
