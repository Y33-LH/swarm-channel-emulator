/* Per-directed-edge channel intervention. UART is serviced only between NETSTEP
 * calls, so a policy change cannot split a DATA/ACK transaction. It is NOT a
 * packet-drop switch. Both path gains and AWGN are applied to actual PL samples. */
typedef struct {unsigned id,enabled,gain_permille,sigma;} EdgePolicy;
static EdgePolicy edge_policy[32];
static unsigned observation_enabled,condition_serial;
static unsigned observation_applied[15],observation_phy[12],observation_meta[16];
static unsigned observation_iq[64][2],observation_count,observation_valid;
static unsigned observation_decode_cycles,observation_iterations,observation_evm_symbols,observation_clipping;
static uint64_t observation_evm_energy;
static unsigned observation_taps[8][5],observation_tap_count,observation_channel_id,observation_sample_rate;
static double observation_channel_model[6];
static double observation_terrain[7];
static double observation_digital_scale;
static unsigned observation_wave[128],observation_wave_count,observation_wave_start;
static uint8_t observation_tx[96],observation_rx[96];
static unsigned edge_trace[128][10],edge_trace_count,edge_trace_overflow;
/* Each uplink owns a small receiver-RAM snapshot independent of NETWATCH. */
#define WALL_SYMBOLS 16
typedef struct {unsigned valid,ms,generation,count,iq[WALL_SYMBOLS][2];} WallCell;
static WallCell wall_cells[16];
static unsigned tap_history_count,tap_history[16][10];
static void edge_reset(void){
 memset(wall_cells,0,sizeof(wall_cells));tap_history_count=0;
 memset(edge_policy,0,sizeof(edge_policy));condition_serial=0;
 observation_valid=observation_count=edge_trace_count=edge_trace_overflow=0;
}
static int edge_command(unsigned n,char **a){
 unsigned i,v[5];uint8_t b[20];
 if(!strcmp(a[0],"LINKOBS")&&n==2){
  if(strcmp(a[1],"0")&&strcmp(a[1],"1")){reply("{\"ok\":0,\"error\":\"OBS_RANGE\"}");return 1;}
  observation_enabled=a[1][0]=='1';observation_valid=observation_count=0;
  reply("{\"ok\":1,\"observation_schema\":1}");return 1;
 }
 if(strcmp(a[0],"LINKCOND")||n!=2)return 0;
 if(!running||strlen(a[1])!=40){reply("{\"ok\":0,\"error\":\"CONDITION_STATE_OR_LENGTH\"}");return 1;}
 for(i=0;i<40;i++){
  char c=a[1][i];unsigned digit;
  if(c>='0'&&c<='9')digit=c-'0';else if(c>='a'&&c<='f')digit=c-'a'+10;
  else {reply("{\"ok\":0,\"error\":\"CONDITION_HEX\"}");return 1;}
  if(!(i&1))b[i/2]=digit<<4;else b[i/2]|=digit;
 }
 for(i=0;i<5;i++)v[i]=get_le32(b+4*i);
 if(!v[0]||v[0]<=condition_serial||v[1]>=32||v[2]>1||v[3]>1000||v[4]>8193){
  reply("{\"ok\":0,\"error\":\"CONDITION_RANGE_OR_STALE_ID\"}");return 1;
 }
 condition_serial=v[0];edge_policy[v[1]].id=v[0];edge_policy[v[1]].enabled=v[2];
 edge_policy[v[1]].gain_permille=v[3];edge_policy[v[1]].sigma=v[4];
 reply("{\"ok\":1,\"type\":\"LINKCOND\",\"schema\":1,\"id\":%u,\"link\":%u,\"enabled\":%u,\"gain_permille\":%u,\"sigma\":%u,\"effective_round\":%u,\"status\":\"ARM_POLICY_ACCEPTED_AWAITING_PL_FRAME\"}",
 v[0],v[1],v[2],v[3],v[4],round_index);return 1;
}
static void edge_apply(unsigned link){
 EdgePolicy *p=&edge_policy[link];unsigned g0,g1;
 if(!p->enabled)return;
 g0=rd(64);g1=rd(120);
 wr(64,(g0*p->gain_permille+500)/1000);
 wr(120,(g1*p->gain_permille+500)/1000);
 /* 8193 preserves the original per-frame noise for attenuation-only trials. */
 if(p->sigma<=8192)wr(68,p->sigma);
 {unsigned j,count=rd(0x31c);for(j=0;j<count&&j<8;j++){unsigned a=0xc00+32*j;int32_t slope=(int32_t)rd(a+16);wr(a,(rd(a)*p->gain_permille+500)/1000);wr(a+16,(uint32_t)(int32_t)((int64_t)slope*p->gain_permille/1000));}}

}
static void edge_observe(unsigned link,const uint8_t *tx,unsigned source){
 unsigned i,count=rd(768),*m=observation_meta,*row;
 if(!observation_enabled)return;
 if(link<16){
  WallCell *cell=&wall_cells[link];
  cell->valid=1;cell->ms=applied[link][1];cell->generation=phy_snapshot[link][3];
  cell->count=phy_snapshot[link][4]?(count<WALL_SYMBOLS?count:WALL_SYMBOLS):0;
  for(i=0;i<cell->count;i++){
   wr(244,i*count/cell->count);wr(248,0);cell->iq[i][0]=rd(252);
   wr(248,1);cell->iq[i][1]=rd(252);
  }
 }
 if(link!=watch_link)return;
 observation_tap_count=rd(0x31c);observation_channel_id=channel_config_id();observation_sample_rate=(unsigned)channel_sample_rate();
 memcpy(observation_channel_model,channel_last_metadata,sizeof(observation_channel_model));
 memcpy(observation_terrain,channel_last_terrain,sizeof(observation_terrain));
 observation_digital_scale=channel_last_scale;
 for(i=0;i<observation_tap_count&&i<8;i++){unsigned j;for(j=0;j<5;j++)observation_taps[i][j]=rd(0xc00+32*i+4*j);}
 if(tap_history_count<16&&observation_tap_count>0&&observation_tap_count<=8){
  unsigned *point=tap_history[tap_history_count++];
  point[0]=applied[link][1];point[1]=observation_tap_count;
  for(i=0;i<point[1];i++)point[2+i]=observation_taps[i][0];
 }
 memcpy(observation_applied,applied[link],sizeof(observation_applied));
 memcpy(observation_phy,phy_snapshot[link],sizeof(observation_phy));
 observation_valid=1;observation_count=rd(100)?(count<64?count:64):0;
 memcpy(observation_tx,tx,96);memset(observation_rx,0,96);
 if(rd(16)&4)sw_payload_read(observation_rx);
 m[0]=edge_policy[link].id;m[1]=tx[1];m[2]=tx[4];m[3]=get_le32(tx+12);
 m[4]=get_le16(tx+16);m[5]=get_le64(tx+20)/1000000;m[6]=tx[30];
 m[7]=rd(16);m[8]=rd(20);m[9]=rd(216);m[10]=rd(220);m[11]=rd(160);m[12]=rd(164);
 m[13]=rd(76);m[14]=source;m[15]=rd(44);
 observation_decode_cycles=rd(224);observation_iterations=rd(228);
 observation_evm_energy=rd(232)|((uint64_t)rd(236)<<32);observation_evm_symbols=rd(240);observation_clipping=rd(156);
 observation_wave_count=0;observation_wave_start=0;
 if(rd(0x318)==0x57415631U){
  unsigned total=rd(0x310);observation_wave_start=rd(100)?rd(0x314)+542*4:0;
  if(total>observation_wave_start){
   observation_wave_count=total-observation_wave_start;if(observation_wave_count>128)observation_wave_count=128;
   wr(248,2);for(i=0;i<observation_wave_count;i++){wr(244,observation_wave_start+i);observation_wave[i]=rd(252);}
  }
 }
 for(i=0;i<observation_count;i++){
  wr(244,i*(count/64?count/64:1));wr(248,0);observation_iq[i][0]=rd(252);
  wr(248,1);observation_iq[i][1]=rd(252);
 }
 /* Existing instruments also receive this coherent DATA frame, not a newer ACK. */
 memcpy(watch_iq,observation_iq,sizeof(watch_iq));watch_iq_count=observation_count;
 watch_iq_ms=applied[link][1];watch_iq_generation=m[15];
 if(edge_trace_count>=128){edge_trace_overflow++;return;}
 row=edge_trace[edge_trace_count++];row[0]=applied[link][1];row[1]=m[0];row[2]=m[15];
 row[3]=m[1];row[4]=m[2];row[5]=m[3];row[6]=m[4];row[7]=rd(100);row[8]=(rd(16)&4)?1:0;row[9]=m[6];
}
static unsigned edge_report(unsigned n){
 unsigned i,j;
 if(!observation_enabled)return n;
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"observation_schema\":1,\"condition_serial\":%u,\"edge_trace_overflow\":%u,\"edge_trace\":[",condition_serial,edge_trace_overflow);
 for(i=0;i<edge_trace_count;i++){
  n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[",i?",":"");
  for(j=0;j<10;j++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",j?",":"",edge_trace[i][j]);
  n+=snprintf(snapshot+n,sizeof(snapshot)-n,"]");
 }
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"observation\":");
 if(!observation_valid){n+=snprintf(snapshot+n,sizeof(snapshot)-n,"null");return n;}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"{\"link\":%u,\"channel_id\":%u,\"sample_rate_hz\":%u,\"taps\":[",watch_link,observation_channel_id,observation_sample_rate);
 for(i=0;i<observation_tap_count&&i<8;i++){n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[",i?",":"");for(j=0;j<5;j++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",j?",":"",observation_taps[i][j]);n+=snprintf(snapshot+n,sizeof(snapshot)-n,"]");}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"model_metadata\":[");
 for(i=0;i<6;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%.6f",i?",":"",observation_channel_model[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"terrain\":[");
 for(i=0;i<7;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%.6f",i?",":"",observation_terrain[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"digital_scale\":%.12f,\"coefficient_limited\":%u,\"applied\":[",observation_digital_scale,(unsigned)observation_channel_model[3]);
 for(i=0;i<15;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",i?",":"",observation_applied[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"phy\":[");
 for(i=0;i<12;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",i?",":"",observation_phy[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"meta\":[");
 for(i=0;i<16;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",i?",":"",observation_meta[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"statistics\":{\"decode_cycles\":%u,\"iterations\":%u,\"evm_energy\":%llu,\"evm_symbols\":%u,\"clipping\":%u},\"iq\":[",observation_decode_cycles,observation_iterations,(unsigned long long)observation_evm_energy,observation_evm_symbols,observation_clipping);
 for(i=0;i<observation_count;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u]",i?",":"",observation_iq[i][0],observation_iq[i][1]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"wave_start_sample\":%u,\"wave_samples\":[",observation_wave_start);
 for(i=0;i<observation_wave_count;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",i?",":"",observation_wave[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"tx_hex\":\"");
 for(i=0;i<96;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%02x",observation_tx[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\",\"rx_hex\":\"");
 for(i=0;(observation_meta[7]&4)&&i<96;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%02x",observation_rx[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\"}");return n;
}
