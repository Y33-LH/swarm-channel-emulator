/* ARM manages queues/time/routes only. Every emitted DATA and ACK is processed
 * by the PL DBPSK/channel/capture/CRC chain; RX bytes alone enter forwarding. */
#include "network.h"
#include "scene.h"
#include "channel_model.h"
#include "payload_driver.h"
#include "xil_io.h"
#include "xtime_l.h"
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "dedup_cache.h"
#define BASE 0x43c00000U
#define QSIZE 192
#define AUDIO_MAX 8192
#define VIDEO_MAX 65536
#define PI 3.14159265358979323846
typedef struct {uint8_t bytes[96];unsigned used,attempt,next_round;} Packet;
typedef struct {unsigned attempts,captured,crc_good,acked,retries,failed,duplicates,bits,errors,clipped;uint64_t cycles;double evm_sum;unsigned evm_count,pre_bits,pre_errors,fec_frames,ack_lost,accepted_bytes,queue_rejected,data_attempts,ack_attempts;} Stats;
static Packet queues[17][QSIZE];
static unsigned applied[32][15];
static unsigned phy_snapshot[32][12],watch_link,watch_iq[64][2],watch_iq_count,watch_iq_ms,watch_iq_generation;
static Stats stats[32];static uint32_t random_state[32];
static uint8_t audio_tx[AUDIO_MAX],audio_rx[AUDIO_MAX],video_tx[VIDEO_MAX],video_rx[VIDEO_MAX];
static uint8_t audio_map[AUDIO_MAX/64],video_map[VIDEO_MAX/64],audio_load[AUDIO_MAX],video_load[VIDEO_MAX];
static unsigned audio_len,video_len,audio_next,video_next,audio_received,video_received;
/* Each repeated reference clip has a distinct on-wire object identity. New
 * objects are explicitly advanced only after the host archives actual RX bytes
 * and all old packets leave the queues. No source bytes repair failed objects. */
static unsigned media_sequence[2],media_total_rx[2],media_total_tx[2];
static unsigned running,duration,round_index,master_seed,run_id,ideal,generated,delivered,ground_bytes,queue_drops,retry_drops,generated_seq,queue_peak,slot_misses;
static const uint8_t heartbeat_tones[16][48]={
 {0x88,0x99,0x68,0x65,0xc9,0xad,0x26,0x63,0xeb,0x9d,0x24,0x84,0xec,0x7c,0x23,0xa5,0xed,0x6a,0x32,0xb6,0xde,0x49,0x42,0xc8,0xce,0x37,0x52,0xda,0xae,0x26,0x63,0xeb,0x9d,0x24,0x84,0xec,0x7c,0x23,0xa5,0xed,0x6a,0x32,0xb6,0xbc,0x69,0x76,0x98,0x88},
 {0x88,0x99,0x67,0x85,0xcb,0x7b,0x33,0xc7,0xce,0x37,0x62,0xeb,0x8d,0x23,0xa5,0xde,0x49,0x42,0xd9,0x9d,0x24,0x94,0xed,0x5a,0x32,0xd8,0xbe,0x26,0x73,0xec,0x7c,0x33,0xc7,0xce,0x37,0x62,0xeb,0x8d,0x23,0xa5,0xde,0x49,0x53,0xc9,0x9b,0x67,0x87,0x88},
 {0x88,0x89,0x67,0x96,0xcc,0x48,0x62,0xeb,0x6c,0x32,0xd8,0xae,0x25,0x94,0xde,0x38,0x62,0xeb,0x7c,0x33,0xc7,0xae,0x25,0x94,0xdd,0x49,0x52,0xeb,0x7c,0x33,0xc7,0xbe,0x25,0x94,0xdd,0x49,0x52,0xeb,0x7c,0x33,0xc7,0xbe,0x36,0x85,0xbb,0x79,0x77,0x88},
 {0x88,0x89,0x66,0xa7,0xac,0x35,0xb5,0xce,0x26,0x93,0xdd,0x38,0x73,0xed,0x4a,0x62,0xeb,0x5b,0x42,0xea,0x7c,0x32,0xd8,0x9d,0x23,0xc6,0xae,0x25,0xb5,0xce,0x26,0x94,0xde,0x38,0x73,0xed,0x49,0x62,0xeb,0x5b,0x42,0xea,0x7c,0x54,0xb8,0x8a,0x77,0x88},
 {0x88,0x89,0x66,0xb8,0x7b,0x43,0xe9,0x7d,0x42,0xe9,0x6c,0x42,0xea,0x6c,0x42,0xea,0x5c,0x52,0xeb,0x5b,0x52,0xeb,0x5b,0x52,0xec,0x4a,0x62,0xec,0x4a,0x62,0xec,0x49,0x72,0xed,0x39,0x72,0xdd,0x38,0x83,0xdd,0x38,0x83,0xcd,0x48,0x85,0xaa,0x78,0x88},
 {0x88,0x89,0x66,0xb9,0x5a,0x73,0xdd,0x38,0x93,0xce,0x26,0xc5,0xae,0x23,0xd8,0x7d,0x42,0xea,0x5b,0x62,0xec,0x38,0x93,0xce,0x26,0xb5,0xae,0x24,0xd7,0x7d,0x42,0xea,0x5b,0x62,0xec,0x39,0x93,0xce,0x26,0xb5,0xae,0x24,0xc7,0x8c,0x65,0xa9,0x79,0x88},
 {0x88,0x79,0x76,0xba,0x48,0xa5,0xae,0x34,0xe8,0x5c,0x62,0xdc,0x28,0xb4,0xae,0x33,0xe9,0x5c,0x62,0xdd,0x27,0xb4,0xae,0x33,0xe9,0x5c,0x62,0xdd,0x27,0xb4,0x9e,0x33,0xe9,0x5b,0x72,0xdd,0x27,0xb5,0x9e,0x33,0xe9,0x5b,0x73,0xbc,0x57,0x97,0x89,0x88},
 {0x88,0x79,0x86,0xab,0x46,0xd7,0x6c,0x72,0xdd,0x26,0xd6,0x6d,0x62,0xdd,0x27,0xc5,0x7d,0x52,0xec,0x28,0xb4,0x8e,0x42,0xeb,0x39,0xb4,0x9e,0x33,0xea,0x3a,0xa3,0xae,0x33,0xe9,0x4b,0x93,0xbe,0x24,0xe8,0x4b,0x82,0xce,0x35,0xc8,0x7a,0x86,0x99,0x88},
 {0x88,0x79,0x96,0x9b,0x55,0xda,0x29,0xc4,0x7e,0x62,0xdd,0x26,0xd7,0x5c,0x82,0xbe,0x34,0xea,0x3a,0xb4,0x8e,0x52,0xdc,0x27,0xd6,0x6d,0x72,0xcd,0x25,0xe8,0x4b,0xa3,0x9e,0x43,0xeb,0x28,0xc5,0x7d,0x62,0xdd,0x26,0xe7,0x5b,0x84,0x9b,0x66,0x98,0x88},
 {0x88,0x78,0x97,0x8b,0x74,0xcc,0x34,0xe9,0x39,0xc4,0x6d,0x72,0xbe,0x34,0xea,0x28,0xd6,0x5c,0x92,0xae,0x43,0xdc,0x27,0xd7,0x4c,0xa3,0x9e,0x52,0xdc,0x26,0xe8,0x3a,0xb4,0x7e,0x62,0xcd,0x34,0xe9,0x39,0xc4,0x6d,0x72,0xbd,0x55,0xb9,0x68,0x97,0x88},
 {0x88,0x78,0xa7,0x6a,0x94,0x8d,0x62,0xcd,0x34,0xeb,0x27,0xe7,0x3b,0xc4,0x6d,0x92,0x9e,0x52,0xcd,0x35,0xea,0x28,0xd6,0x4b,0xb3,0x7e,0x82,0xae,0x43,0xdc,0x25,0xe9,0x29,0xd6,0x4c,0xa3,0x7e,0x72,0xbe,0x43,0xdc,0x26,0xd8,0x49,0xa6,0x7a,0x87,0x88},
 {0x88,0x78,0xa7,0x5a,0xb5,0x5c,0xa3,0x7e,0x82,0x9e,0x62,0xbe,0x43,0xcc,0x34,0xeb,0x26,0xe9,0x28,0xe7,0x3a,0xd5,0x4c,0xb3,0x6d,0x92,0x8e,0x72,0xae,0x53,0xcd,0x34,0xdb,0x26,0xe9,0x28,0xe7,0x2a,0xd5,0x4c,0xc4,0x5d,0x93,0x8c,0x85,0x8a,0x87,0x88},
 {0x88,0x78,0xa8,0x59,0xc7,0x39,0xe6,0x3a,0xd5,0x3b,0xd5,0x3c,0xd4,0x4c,0xc4,0x4d,0xb3,0x5d,0xb3,0x5d,0xa3,0x6e,0xa2,0x7e,0x92,0x7e,0x82,0x8e,0x82,0x9e,0x72,0x9e,0x62,0xae,0x62,0xbd,0x53,0xbd,0x43,0xcd,0x44,0xcc,0x44,0xbb,0x56,0xa9,0x77,0x88},
 {0x88,0x78,0xa8,0x57,0xc9,0x36,0xea,0x35,0xdb,0x35,0xdc,0x34,0xcc,0x44,0xcd,0x53,0xbd,0x53,0xad,0x62,0xae,0x72,0x9e,0x72,0x8e,0x82,0x7e,0x92,0x7e,0xa2,0x6e,0xa2,0x5d,0xb3,0x5d,0xc3,0x4d,0xc4,0x3c,0xd4,0x3c,0xd5,0x4b,0xc6,0x59,0xa7,0x78,0x88},
 {0x88,0x78,0xa9,0x56,0xbb,0x54,0xad,0x72,0x8e,0x92,0x6e,0xb3,0x4d,0xd4,0x3b,0xe6,0x29,0xe8,0x27,0xda,0x35,0xcc,0x53,0xad,0x72,0x8e,0x92,0x6e,0xb3,0x4d,0xd4,0x3b,0xe6,0x29,0xe8,0x27,0xea,0x35,0xcc,0x53,0xbd,0x72,0x8d,0x84,0x7b,0x96,0x79,0x88},
 {0x88,0x78,0xa9,0x66,0x9c,0x93,0x6e,0xc3,0x3c,0xe6,0x29,0xe9,0x35,0xbc,0x63,0x8e,0xa2,0x5d,0xd4,0x2b,0xe7,0x27,0xda,0x44,0xad,0x72,0x7e,0xb2,0x4d,0xd5,0x2a,0xe8,0x36,0xcb,0x53,0x9e,0x92,0x6e,0xc3,0x3c,0xe6,0x29,0xd9,0x56,0xab,0x76,0x89,0x88}
};
static uint8_t ground_audio[17][48],ground_audio_valid[17];
static unsigned ground_seq[17],ground_seen_ms[17],ground_updates[17];static int32_t observed[17][3];
static uint64_t e2e_delay_ns,e2e_max_ns;static unsigned delivered_hb,delivered_alarm;
static unsigned alarm_events[4][4],alarm_count;
static unsigned fatal_code,ack_drop_once;static unsigned ground_generated_ms[17];
static unsigned tdma_max_samples,tdma_max_pl_cycles,tdma_max_arm_us,tdma_pl_overruns,tdma_arm_overruns;
static void tdma_account(unsigned samples,unsigned pl_cycles,XTime started){
 XTime now;unsigned arm_us;XTime_GetTime(&now);arm_us=(unsigned)((now-started)*1000000/COUNTS_PER_SECOND);
 if(samples>tdma_max_samples)tdma_max_samples=samples;if(pl_cycles>tdma_max_pl_cycles)tdma_max_pl_cycles=pl_cycles;if(arm_us>tdma_max_arm_us)tdma_max_arm_us=arm_us;
 if(samples/channel_sample_rate()+.00005>.005)slot_misses++;
 if(pl_cycles/62500000.+.00005>.005)tdma_pl_overruns++;
 if(arm_us>5000)tdma_arm_overruns++;
}
static unsigned fec_enabled=1,load_pps,load_generated,load_delivered,load_bytes,load_accum;
/* Histogram bins are 10 model-ms; last bin is overflow. P95 is an upper bound. */
static unsigned delay_hist[6002],timely_delivered,late_delivered,loss_expired,loss_attempt_limit;
static unsigned timely_by_type[8],received_by_type[8],generated_by_type[8];
static unsigned telemetry_full=1,telemetry_compact=0;
static unsigned delay_p95(void){unsigned i,n=0,target=(delivered*95+99)/100;if(!delivered)return 0;for(i=0;i<6002;i++){n+=delay_hist[i];if(n>=target)return i==6001?0xffffffffU:(i+1)*10;}return 0xffffffffU;}
static uint8_t external_received[96];static unsigned external_received_valid,external_injected;
typedef struct {unsigned id,target,opcode,value,expiry_ms,ground_status,ground_received_ms,executions,ground_period,ground_pause,ground_rate;} GroundCommand;
static GroundCommand commands[64];static unsigned command_count,last_command_id;
static uint32_t get_le32(const uint8_t*b);
/* Bounded diagnostic trace; never substitutes for a received command result. */
static unsigned command_trace[256][10],command_trace_count,command_ack_drop;
static void trace_command(const uint8_t*b,unsigned node,unsigned dest,uint64_t now,unsigned captured,unsigned crc,unsigned accepted,unsigned acked){
 unsigned *p;if(b[1]!=6&&b[1]!=7)return;
 if(command_trace_count>=256){memmove(command_trace,command_trace+1,255*sizeof(command_trace[0]));command_trace_count=255;}
 p=command_trace[command_trace_count++];p[0]=now/1000000;p[1]=get_le32(b+32);p[2]=b[1];p[3]=node;p[4]=dest;p[5]=captured;p[6]=crc;p[7]=accepted;p[8]=acked;p[9]=b[30];
}
static unsigned heartbeat_rounds[17],media_paused[17],media_rate[17];
static XTime run_start;static char snapshot[24576];
/* Return stored length, not snprintf's would-have-written length. This keeps
 * subsequent append pointers within the buffer even at maximum trace size. */
static unsigned telemetry_overflow;
static int bounded_print(char *dest,size_t capacity,const char *format,...){
 int n;va_list ap;if(!capacity){telemetry_overflow=1;return 0;}
 va_start(ap,format);n=vsnprintf(dest,capacity,format,ap);va_end(ap);
 if(n<0){telemetry_overflow=1;dest[0]=0;return 0;}
 if((unsigned)n>=capacity){telemetry_overflow=1;return capacity-1;}return n;
}
#define snprintf bounded_print
static unsigned rd(unsigned o){return Xil_In32(BASE+o);}static void wr(unsigned o,unsigned v){Xil_Out32(BASE+o,v);}
static uint16_t get_le16(const uint8_t*b){return b[0]|((uint16_t)b[1]<<8);}static uint32_t get_le32(const uint8_t*b){return b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);}
static uint64_t get_le64(const uint8_t*b){return get_le32(b)|((uint64_t)get_le32(b+4)<<32);}static void w16(uint8_t*b,unsigned n){b[0]=n;b[1]=n>>8;}static void w32(uint8_t*b,uint32_t n){unsigned i;for(i=0;i<4;i++)b[i]=n>>(i*8);}static void w64(uint8_t*b,uint64_t n){w32(b,(uint32_t)n);w32(b+4,n>>32);}
static unsigned next_node(unsigned n){return n%4?n+1:0;}static unsigned priority(unsigned t){return t==1?0:t==2?1:(t==6||t==7)?2:3;}
static int node_off(unsigned n,double t){return scene_node_off(n,t);}
static int enqueue(unsigned node,const uint8_t *b){unsigned i,count=0;for(i=0;i<QSIZE;i++)count+=queues[node][i].used!=0;if(count>=QSIZE||(priority(b[1])>=2&&count>=QSIZE-8))return 0;for(i=0;i<QSIZE;i++)if(!queues[node][i].used){memcpy(queues[node][i].bytes,b,96);queues[node][i].used=1;queues[node][i].attempt=0;queues[node][i].next_round=0;if(count+1>queue_peak)queue_peak=count+1;return 1;}return 0;}
static Packet *choose(unsigned node,int retry_only){unsigned i;Packet *best=0;for(i=0;i<QSIZE;i++){Packet*p=&queues[node][i];if(!p->used||p->next_round>round_index||(retry_only&&!p->attempt))continue;if(!best||priority(p->bytes[1])<priority(best->bytes[1])||(priority(p->bytes[1])==priority(best->bytes[1])&&get_le64(p->bytes+20)<get_le64(best->bytes+20)))best=p;}return best;}
static int duplicate(unsigned node,const uint8_t*b){return seen_contains(node,b[4],get_le32(b+12),get_le16(b+16));}
static void remember(unsigned node,const uint8_t*b){seen_insert(node,b[4],get_le32(b+12),get_le16(b+16));}
static void create_packet(uint8_t*b,unsigned src,unsigned type,unsigned seq,unsigned frag,unsigned count,uint64_t now,const uint8_t*payload,unsigned len){memset(b,0,96);b[0]=1;b[1]=type;b[3]=5;b[4]=src;b[5]=0;b[6]=src;b[7]=next_node(src);w32(b+8,run_id);w32(b+12,seq);w16(b+16,frag);w16(b+18,count);w64(b+20,now);w16(b+28,len);memcpy(b+32,payload,len);}
#include "hardware_nodes.h"
static unsigned bounded_gain(double g){if(g<0)return 0;if(g>1)return 32768;return (unsigned)(g*32768+.5);}
static uint32_t phase_word(double p){double w=fmod(p/(2*PI),1.);if(w<0)w+=1.;return (uint32_t)(w*4294967296.);}
/* ARM model provenance captured with DATA, distinct from PL register readback. */
static double channel_last_metadata[6];
static double channel_last_terrain[7];
static double channel_last_scale=1;
#include "link_control.h"
static void config_link(unsigned link,double t,int ack){LinkConfig c;ChannelFrame cf;unsigned k;double fs=channel_sample_rate();scene_link(link,t,master_seed,&c);channel_frame(link,t,master_seed,&c,&cf);
 channel_last_metadata[0]=ideal?0:cf.loss_db;channel_last_metadata[1]=ideal?0:cf.rain_db_km;
 channel_last_metadata[2]=ideal||channel_configuration()[1]==2?0:c.geometric_doppler;
 channel_last_metadata[3]=ideal?0:cf.clamped;channel_last_metadata[4]=channel_configuration()[1];channel_last_metadata[5]=cf.model;
 memcpy(channel_last_terrain,cf.terrain,sizeof(channel_last_terrain));
 channel_last_scale=ideal||!channel_configuration()[1]?1:channel_digital_scale(&cf,c.sigma);
 // ACK has a separate 50000-PL-cycle timeout, and the receiver limits
 // missing-ACK search to 10000 model samples. These bounds keep
 // DATA + turnaround + ACK inside the fixed 40000-sample / 5ms slot.
 // Valid full-FEC ACK processing is below this budget and is verified on board.
 wr(0,4);wr(0x308,0);wr(12,0);wr(48,ack?50000:1000000);wr(64,ideal?32768:bounded_gain(c.gain0));wr(68,ideal?0:(unsigned)(c.sigma+.5));wr(80,link*7%61);
 wr(84,ideal?0:phase_word(c.phase));wr(88,random_state[link]);wr(92,ideal?0:(uint32_t)(int32_t)llround(c.cfo*4294967296./8000000.));wr(96,!c.available||(ack&&ack_drop_once));if(ack&&ack_drop_once)ack_drop_once--;
 wr(112,ideal?0:(unsigned)(c.delay+.5));wr(116,ack!=0);wr(120,ideal?0:bounded_gain(c.gain1));wr(124,ideal?0:(unsigned)(c.echo_delay+.5));
 wr(128,ideal?0:phase_word(c.echo_phase));wr(132,ideal?0:(uint32_t)(int32_t)llround(c.echo_cfo*4294967296./8000000.));wr(136,0);wr(140,0);wr(192,fec_enabled);
 wr(0x31c,0);
 if(channel_configuration()[1]&&!ideal){
  wr(68,(unsigned)llround(c.sigma*channel_last_scale));
  for(k=0;k<cf.count;k++){
   ChannelTap *a=&cf.taps[k];unsigned base=0xc00+32*k;
   if(a->delay<0||a->delay>1023||!isfinite(a->gain)||!isfinite(a->cfo)||fabs(a->cfo)>100000){fatal_code=230;running=0;return;}
   wr(base,bounded_gain(a->gain*channel_last_scale));wr(base+4,(unsigned)llround(a->delay));wr(base+8,phase_word(a->phase));
   wr(base+12,(uint32_t)(int32_t)llround(a->cfo*4294967296./fs));
   wr(base+16,(uint32_t)(int32_t)llround(a->ramp_per_second*channel_last_scale*2147483648./fs));
  }
  wr(0x31c,cf.count);
  /* Legacy summary fields mirror the first two applied taps; full tap bank is
   * captured with the very same DATA generation below. */
  wr(64,rd(0xc00));wr(84,rd(0xc08));wr(92,rd(0xc0c));wr(112,rd(0xc04));wr(136,rd(0xc10));
  wr(120,cf.count>1?rd(0xc20):0);wr(128,cf.count>1?rd(0xc28):0);wr(132,cf.count>1?rd(0xc2c):0);
  /* The old 6-bit excess-delay register cannot represent every manual profile.
   * It remains zero in multi-tap mode; plots must use the full tap bank. */
  wr(124,0);wr(140,cf.count>1?rd(0xc30):0);
 }
 edge_apply(link);
 /* Read back writable configuration registers; these are applied model values,
  * distinct from pilot-estimated receive values in PHYSTATS. */
 applied[link][0]=1;applied[link][1]=(unsigned)llround(t*1000);applied[link][2]=ack;
 applied[link][3]=rd(64);applied[link][4]=rd(120);applied[link][5]=rd(68);
 applied[link][6]=rd(112);applied[link][7]=rd(124);applied[link][8]=rd(84);applied[link][9]=rd(128);
 applied[link][10]=rd(92);applied[link][11]=rd(132);applied[link][12]=rd(96);applied[link][13]=rd(88);applied[link][14]=(unsigned)llround(c.distance*1000);

}
static int transfer(unsigned link,double t,const uint8_t*tx,int ack,uint8_t*rx,unsigned source){Stats*s=&stats[link];unsigned i,n=ack?12:96,code;uint64_t energy;double evm;
 config_link(link,t,ack);if(fatal_code)return -1;wr(0x304,source);
 if(source){wr(4,ack?12:get_le16(tx+28));wr(8,get_le32(tx+12));code=rd(0x34);}else code=sw_payload_prepare(tx,ack?12:get_le16(tx+28),get_le32(tx+12));if(!code)code=sw_payload_start();
 if(code||!sw_payload_wait(100)){running=0;fatal_code=code?code:100;return -1;}
 random_state[link]=rd(144);s->attempts++;if(ack)s->ack_attempts++;else s->data_attempts++;s->captured+=rd(100);s->bits+=rd(164);s->errors+=rd(160);s->clipped+=rd(156);s->cycles+=rd(40);
 s->pre_bits+=rd(220);s->pre_errors+=rd(216);s->fec_frames+=rd(228)==2;
 energy=rd(232)|((uint64_t)rd(236)<<32);i=rd(240);
 if(i&&rd(100)){evm=sqrt(energy/(i*67108864.));s->evm_sum+=evm;s->evm_count++;}
 {unsigned *p=phy_snapshot[link],j,count;
  p[0]=1;p[1]=(unsigned)llround(t*1000);p[2]=ack;p[3]=rd(44);p[4]=rd(100);p[5]=rd(196);p[6]=rd(200);p[7]=rd(204);p[8]=rd(208);p[9]=rd(212);p[10]=rd(228);p[11]=rd(16);
  /* One decimated DATA snapshot per >=10 model seconds on the selected link.
   * This is an actual receiver RAM sample, not generated constellation points. */
  if(!observation_enabled&&!ack&&link==watch_link&&rd(100)&&(!watch_iq_count||p[1]>=watch_iq_ms+10000)){
   count=rd(768);watch_iq_count=count<64?count:64;watch_iq_ms=p[1];watch_iq_generation=p[3];
   for(j=0;j<watch_iq_count;j++){wr(244,j*(count/64?count/64:1));wr(248,0);watch_iq[j][0]=rd(252);wr(248,1);watch_iq[j][1]=rd(252);}
  }
 }
 if(!ack)edge_observe(link,tx,source);
 if(!(rd(16)&4)){s->failed++;return 0;}
 if(rd(28)!=n){running=0;fatal_code=101;return -1;}sw_payload_read(rx);s->crc_good++;return 1;
}
static void account_delivery(uint8_t*b,uint64_t received_at);
static int execute_command(unsigned node,uint8_t*b,uint64_t now){
 unsigned id=get_le32(b+32),op=b[36],value=get_le32(b+40),expiry=get_le32(b+44),status=2,i,used=0,j;GroundCommand*c=0;uint8_t payload[20],response[96];
 for(i=0;i<command_count;i++)if(commands[i].id==id&&commands[i].target==node)c=&commands[i];
 if(!c)return 0;
 /* Reserve space before any mutation: a failed queue admission is retryable and cannot execute twice. */
 for(i=0;i<QSIZE;i++)if(!queues[node][i].used)break;
 if(i==QSIZE)return 0;
 if(now/1000000>expiry)status=4;
 else if(op==1){} /* Return actual heartbeat/media state. */
 else if(op==2&&value>=100&&value<=10000&&value%100==0)heartbeat_rounds[node]=value/100;
 else if(op==3&&value<=1)media_paused[node]=value;
 else if(op==4&&value>=1&&value<=30)media_rate[node]=value;
 else if(op==5&&scene_altitude(node,value,now/1e9,master_seed)){}
 else status=3;
 memset(payload,0,sizeof(payload));w32(payload,id);w32(payload+4,status);w32(payload+8,heartbeat_rounds[node]*100);w32(payload+12,media_paused[node]);w32(payload+16,media_rate[node]);
 create_packet(response,node,7,++generated_seq,0,1,now,payload,20);
 /* Priority controls reserve 8 entries; command response uses the reserved capacity. */
 memcpy(queues[node][i].bytes,response,96);queues[node][i].used=1;queues[node][i].attempt=0;queues[node][i].next_round=0;
 for(j=0;j<QSIZE;j++){used+=queues[node][j].used!=0;}
 if(used>queue_peak)queue_peak=used;
 generated++;generated_by_type[7]++;c->executions++;
 return 1;
}
static int deliver(unsigned node,uint8_t*b,uint64_t received_at){unsigned type=b[1],src=b[4],len=get_le16(b+28),frag=get_le16(b+16),seq=get_le32(b+12);
 if(get_le32(b+8)!=run_id||len>64||len==0)return 0;
 if(type==6){
  if(src!=0||b[5]<1||b[5]>16||len!=16||!node)return 0;
  if(node==b[5]&&hw_base(node)){int accepted=hw_received_command(node,b,received_at);if(accepted==1)account_delivery(b,received_at);return accepted;}
  if(duplicate(node,b))return 2;
  if(node==b[5]){unsigned i;for(i=0;i<command_count;i++)if(commands[i].id==get_le32(b+32)&&commands[i].target==node&&commands[i].executions)return 2;if(!execute_command(node,b,received_at))return 0;remember(node,b);account_delivery(b,received_at);return 1;}
  if(b[3]==0){return 0;}
  b[3]--;if(!enqueue(node,b))return 0;remember(node,b);return 1;
 }
 if(src<1||src>16||b[5]!=0)return 0;
 if(duplicate(node,b))return 2;
 if(node){if(b[3]==0){return 0;}
  b[3]--;if(!enqueue(node,b))return 0;remember(node,b);return 1;}
 if(type==1&&(len==16||len==64)){ground_audio_valid[src]=(len==64);if(len==64)memcpy(ground_audio[src],b+48,48);ground_generated_ms[src]=(unsigned)(get_le64(b+20)/1000000);ground_seq[src]=seq;ground_seen_ms[src]=(unsigned)(received_at/1000000);ground_updates[src]++;observed[src][0]=(int32_t)get_le32(b+32);observed[src][1]=(int32_t)get_le32(b+36);observed[src][2]=(int32_t)get_le32(b+40);delivered_hb++;}
 else if(type==2){delivered_alarm++;if(alarm_count<4){unsigned *event=alarm_events[alarm_count++];event[0]=b[32];event[1]=src;event[2]=(unsigned)(get_le64(b+20)/1000000);event[3]=(unsigned)(received_at/1000000);}}
 else if(type==3||type==4){unsigned total=type==3?audio_len:video_len;uint8_t*map=type==3?audio_map:video_map;uint8_t*data=type==3?audio_rx:video_rx;
  if(seq!=media_sequence[type-3]||frag*64+len>total||get_le16(b+18)!=(total+63)/64)return 0;
  if(map[frag])return 2;
  memcpy(data+frag*64,b+32,len);map[frag]=1;media_total_rx[type-3]+=len;if(type==3)audio_received+=len;else video_received+=len;
 }else if(type==7&&len==20){unsigned i;for(i=0;i<command_count;i++)if(commands[i].id==get_le32(b+32)&&commands[i].target==src){commands[i].ground_status=get_le32(b+36);commands[i].ground_received_ms=received_at/1000000;commands[i].ground_period=get_le32(b+40);commands[i].ground_pause=get_le32(b+44);commands[i].ground_rate=get_le32(b+48);break;}if(i==command_count)return 0;}
 else if(type==5&&len>=1&&len<=64){load_delivered++;load_bytes+=len;}else return 0;
 if(b[2]&1){memcpy(external_received,b,96);external_received_valid=1;}
 remember(0,b);account_delivery(b,received_at);return 1;
}
static void account_delivery(uint8_t*b,uint64_t received_at){unsigned type=b[1];uint64_t delay;delivered++;ground_bytes+=get_le16(b+28);delay=received_at-get_le64(b+20);e2e_delay_ns+=delay;
 {unsigned bin=(unsigned)(delay/10000000ULL);unsigned limit=type==1?2000:type==2?1000:5000;if(bin>6001)bin=6001;delay_hist[bin]++;received_by_type[type]++;if(delay<=(uint64_t)limit*1000000){timely_delivered++;timely_by_type[type]++;}else late_delivered++;}
 if(delay>e2e_max_ns)e2e_max_ns=delay;}
static void attempt(unsigned node,uint64_t slot_ns,int retry_only){Packet*p,hardware_packet;uint8_t tx[96],rx[96],ack_tx[96],ack_rx[96];unsigned dest,link,accepted=0,captured,hardware=hw_base(node);int good;double t=slot_ns/1e9;unsigned duration_samples,data_cycles;XTime transaction_start;
 if(hardware){if(!hw_choose(node,retry_only))return;p=&hardware_packet;hw_peek(node,p->bytes);p->used=1;p->attempt=rd(hardware+0x7c);p->next_round=0;}else {p=choose(node,retry_only);if(!p)return;}
 if(slot_ns-get_le64(p->bytes+20)>=60000000000ULL){p->used=0;retry_drops++;loss_expired++;return;}
 if(p->bytes[5]){dest=node?node-1:((p->bytes[5]-1)/4+1)*4;link=dest-1+16;}else {if(!node)return;dest=next_node(node);link=node-1;}
 if(node_off(node,t))return;
 memcpy(tx,p->bytes,96);tx[6]=node;tx[7]=dest;tx[30]=p->attempt;
 if(p->attempt)stats[link].retries++;
 XTime_GetTime(&transaction_start);good=transfer(link,t,tx,0,rx,hw_source(node));if(good<0)return;
 duration_samples=rd(104);data_cycles=rd(40);captured=rd(100);
 if(good){
  // Link identity validation uses received fields; original TX bytes never fill gaps.
  if(rx[6]!=node||rx[7]!=dest||get_le32(rx+8)!=run_id||get_le32(rx+12)!=get_le32(tx+12)||get_le16(rx+16)!=get_le16(tx+16))accepted=0;
  else accepted=deliver(dest,rx,slot_ns+(uint64_t)llround(duration_samples*1e9/channel_sample_rate()));
  if(accepted==2)stats[link].duplicates++;else if(accepted==1)stats[link].accepted_bytes+=get_le16(rx+28);else stats[link].queue_rejected++;
  memset(ack_tx,0,96);w32(ack_tx,run_id);w32(ack_tx+4,get_le32(rx+12));w16(ack_tx+8,get_le16(rx+16));ack_tx[10]=dest;ack_tx[11]=accepted?0:1;
  if(tx[1]==6&&dest==tx[5]&&command_ack_drop==get_le32(tx+32)){ack_drop_once=1;command_ack_drop=0;}
  good=transfer(link^16,t+duration_samples/channel_sample_rate()+.00005,ack_tx,1,ack_rx,(hw_base(dest)&&(rd(hw_base(dest)+0x40)&8))?hw_source(dest)+2:0);
  if(good<0)return;
  tdma_account(duration_samples+rd(104),data_cycles+rd(40),transaction_start);
  if(good&&get_le32(ack_rx)==run_id&&get_le32(ack_rx+4)==get_le32(tx+12)&&get_le16(ack_rx+8)==get_le16(tx+16)&&ack_rx[10]==dest&&ack_rx[11]==0){trace_command(tx,node,dest,slot_ns,captured,1,accepted,1);p->used=0;stats[link].acked++;if(hardware&&(rd(hardware+0x40)&4)){running=0;fatal_code=222;}return;}
  trace_command(tx,node,dest,slot_ns,captured,1,accepted,0);
  stats[link].ack_lost++;
 }else { /* Missing DATA still reserves the bounded missing-ACK search window. */
  tdma_account(duration_samples+10000,data_cycles,transaction_start);trace_command(tx,node,dest,slot_ns,captured,0,0,0);
 }
 if(hardware){unsigned limit=rd(hardware+0x7c)>=63;wr(hardware,4);hw_account(node);if(limit){loss_expired--;loss_attempt_limit++;}return;}
 // Bounded store-and-forward: preserve the original generation timestamp.
 // Persistent outages retain frames for <=60 model seconds, max64 attempts.
 // After two fast retries, back off by 1 s to avoid repeatedly probing a fade.
 p->attempt++;p->next_round=round_index+(p->attempt<=2?1:10);
 if(p->attempt>=64||slot_ns-get_le64(p->bytes+20)>=60000000000ULL){p->used=0;retry_drops++;if(slot_ns-get_le64(p->bytes+20)>=60000000000ULL)loss_expired++;else loss_attempt_limit++;}
}
static void generate(unsigned round){unsigned node,burst;uint8_t p[64],b[96];uint64_t now=(uint64_t)round*100000000;double t=round*.1;
 load_accum+=load_pps;
 while(load_accum>=10){unsigned j;load_accum-=10;for(node=1;node<=13;node+=4){if(hw_base(node))continue;for(j=0;j<64;j++)p[j]=(uint8_t)(generated_seq+j+node);create_packet(b,node,5,++generated_seq,0,1,now,p,64);generated++;generated_by_type[b[1]]++;load_generated++;if(!enqueue(node,b))queue_drops++;}}
 for(node=1;node<=16;node++)if(!hw_base(node)&&round%heartbeat_rounds[node]==0&&!node_off(node,t)&&node!=(unsigned)scene_configuration()[14]){Vec3 v=scene_position(node,t,master_seed);w32(p,(int32_t)llround(v.x*1000));w32(p+4,(int32_t)llround(v.y*1000));w32(p+8,(int32_t)llround(v.z*1000));w32(p+12,round);memcpy(p+16,heartbeat_tones[node-1],48);create_packet(b,node,1,++generated_seq,0,1,now,p,64);generated++;generated_by_type[b[1]]++;if(!enqueue(node,b))queue_drops++;}
 hw_tick(9,round);hw_tick(13,round);
 if(scene_configuration()[11]){unsigned ev;const double at[4]={330,370,660,700};for(ev=0;ev<4;ev++)if(scene_time(t)>=at[ev]&&scene_time(t-.1)<at[ev]){unsigned src=ev<2?3:12;p[0]=ev+1;w32(p+1,round);create_packet(b,src,2,++generated_seq,0,1,now,p,5);generated++;generated_by_type[b[1]]++;if(!enqueue(src,b))queue_drops++;}}
 for(burst=0;burst<(media_rate[1]+9-round%10)/10;burst++)if(round>=50&&!media_paused[1]&&audio_next<(audio_len+63)/64){unsigned len=audio_len-audio_next*64;if(len>64)len=64;create_packet(b,1,3,media_sequence[0],audio_next,(audio_len+63)/64,now,audio_tx+audio_next*64,len);if(enqueue(1,b)){audio_next++;media_total_tx[0]+=len;generated++;generated_by_type[b[1]]++;}}
 for(burst=0;burst<(media_rate[5]+9-round%10)/10;burst++)if(round>=100&&!media_paused[5]&&video_next<(video_len+63)/64){unsigned len=video_len-video_next*64;if(len>64)len=64;create_packet(b,5,4,media_sequence[1],video_next,(video_len+63)/64,now,video_tx+video_next*64,len);if(enqueue(5,b)){video_next++;media_total_tx[1]+=len;generated++;generated_by_type[b[1]]++;}}
}
#include "telemetry_wire.h"
static unsigned media_pending(unsigned kind,unsigned seq){unsigned node,j,n=0;for(node=0;node<17;node++)for(j=0;j<QSIZE;j++)if(queues[node][j].used&&queues[node][j].bytes[1]==kind&&get_le32(queues[node][j].bytes+12)==seq)n++;return n;}
static void report(void){unsigned i,n=0,pending=0;telemetry_overflow=0;if(fatal_code){reply("{\"ok\":0,\"type\":\"NETWORK_ERROR\",\"code\":%u}",fatal_code);return;}XTime now;XTime_GetTime(&now);for(i=0;i<17*QSIZE;i++)pending+=((Packet*)queues)[i].used!=0;pending+=rd(0x4a0)+rd(0x8a0);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"{\"ok\":1,\"type\":\"NETWORK\",\"version\":%u,\"run_id\":%u,\"seed\":%u,\"running\":%u,\"round\":%u,\"duration_s\":%u,\"wall_ms\":%llu,\"generated\":%u,\"delivered\":%u,\"payload_bytes\":%u,\"queue_drops\":%u,\"retry_drops\":%u,\"pending\":%u,\"queue_peak\":%u,\"slot_misses\":%u,\"delay_sum_ns\":%llu,\"delay_max_ns\":%llu,\"hb\":%u,\"alarms\":%u,\"media\":[%u,%u,%u,%u],",SWARM_PL_VERSION,run_id,master_seed,running,round_index,duration,(unsigned long long)((now-run_start)*1000/COUNTS_PER_SECOND),generated,delivered,ground_bytes,queue_drops,retry_drops,pending,queue_peak,slot_misses,(unsigned long long)e2e_delay_ns,(unsigned long long)e2e_max_ns,delivered_hb,delivered_alarm,audio_received,audio_len,video_received,video_len);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\"media_totals\":[%u,%u,%u,%u],\"media_objects\":[[3,%u,%u,%u,%u],[4,%u,%u,%u,%u]],\"nodes\":[",media_total_rx[0],media_total_tx[0],media_total_rx[1],media_total_tx[1],media_sequence[0],audio_next,(audio_len+63)/64,media_pending(3,media_sequence[0]),media_sequence[1],video_next,(video_len+63)/64,media_pending(4,media_sequence[1]));
 for(i=1;i<=16;i++){Vec3 v=scene_position(i,round_index*.1,master_seed);n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%d,%d,%d,%d,%d,%d,%u,%u,%u,%u]",i==1?"":",",i,(int)llround(v.x*1000),(int)llround(v.y*1000),(int)llround(v.z*1000),(int)observed[i][0],(int)observed[i][1],(int)observed[i][2],ground_seen_ms[i],ground_seq[i],ground_updates[i],ground_generated_ms[i]);}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"links\":[");
 for(i=0;telemetry_full==1&&!telemetry_compact&&i<32;i++){Stats*s=&stats[i];n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u]",i?",":"",s->attempts,s->captured,s->crc_good,s->acked,s->retries,s->failed,s->duplicates,s->bits,s->errors,s->clipped,(unsigned long long)s->cycles,s->evm_count,s->evm_count?(unsigned)(s->evm_sum/s->evm_count*1000000):0,s->pre_bits,s->pre_errors,s->fec_frames,s->ack_lost,s->accepted_bytes,s->queue_rejected,s->data_attempts,s->ack_attempts);}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"]");
 if(telemetry_compact&&telemetry_full){wire_used=0;for(i=0;i<32;i++)wire_stats(&stats[i]);n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"links_codec\":\"uvarint-32x21-v1\",\"links_data\":\"");n+=wire_base64(snapshot+n,sizeof(snapshot)-n);n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\"");}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"alarm_events\":[");
 for(i=0;i<alarm_count;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u,%u,%u]",i?",":"",alarm_events[i][0],alarm_events[i][1],alarm_events[i][2],alarm_events[i][3]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"scene_profile\":\"full_phy_v1\",\"reference_snr_db\":%.2f,\"echo_offset_db\":-6,\"network_major_buffers_bytes\":%u,\"profile\":\"%s\",\"ideal\":%u,\"load_pps_per_source\":%u,\"load_generated\":%u,\"load_delivered\":%u,\"load_bytes\":%u}",scene_configuration()[10]/100.,(unsigned)(sizeof(queues)+sizeof(seen)+sizeof(seen_buckets)+sizeof(stats)+sizeof(random_state)+sizeof(audio_tx)+sizeof(audio_rx)+sizeof(video_tx)+sizeof(video_rx)+sizeof(audio_load)+sizeof(video_load)+sizeof(snapshot)+sizeof(applied)+sizeof(delay_hist)+sizeof(commands)+sizeof(external_received)),fec_enabled?"DBPSK_SCR_INT_CONV_TURBO2":"DBPSK_RECT_RAW",ideal,load_pps,load_generated,load_delivered,load_bytes);

 n+=snprintf(snapshot+n-1,sizeof(snapshot)-n+1,",\"communication_ms\":%u,\"scene_ms\":%.0f,\"scene_time_scale\":%u}",round_index*100,scene_time(round_index*.1)*1000,(unsigned)(scene_configuration()[15]?scene_configuration()[15]:1))-1;
 /* Append by replacing only the final closing brace, keeping old fields compatible. */
 if(n>0&&snapshot[n-1]=='}')n--;
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"channel_id\":%u,\"sample_rate_hz\":%.0f",channel_config_id(),channel_sample_rate());
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"config_id\":%u,\"protocol\":23,\"telemetry_full\":%u,\"timely_delivered\":%u,\"late_delivered\":%u,\"p95_upper_ms\":%u,\"p95_bin_ms\":10,\"expired\":%u,\"attempt_limit\":%u,\"timely_deadlines_ms\":[2000,1000,5000],\"business_counts\":[",(unsigned)scene_config_id(),telemetry_full,timely_delivered,late_delivered,delay_p95(),loss_expired,loss_attempt_limit);
 for(i=1;i<=7;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u,%u,%u]",i==1?"":",",i,generated_by_type[i],received_by_type[i],timely_by_type[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"applied_links\":[");
 for(i=0;telemetry_full==1&&!telemetry_compact&&i<32;i++){unsigned *a=applied[i];n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u]",i?",":"",a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11],a[12],a[13],a[14]);}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"]");
 if(telemetry_full==1&&telemetry_compact){unsigned j,k;wire_used=0;for(i=0;i<32;i++)for(j=0;j<15;j++)for(k=0;k<4;k++)wire_bytes[wire_used++]=(applied[i][j]>>(8*k))&255;
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"applied_codec\":\"le32-32x15-v1\",\"applied_data\":\"");n+=wire_base64(snapshot+n,sizeof(snapshot)-n);n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\"");}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"watch_link\":%u,\"watch_phy\":[",watch_link);
 for(i=0;i<12;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s%u",i?",":"",(observation_enabled&&observation_valid?observation_phy:phy_snapshot[watch_link])[i]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"],\"watch_iq_ms\":%u,\"watch_iq_generation\":%u,\"watch_iq\":[",watch_iq_ms,watch_iq_generation);
 for(i=0;!telemetry_compact&&i<watch_iq_count;i++)n+=snprintf(snapshot+n,sizeof(snapshot)-n,"%s[%u,%u]",i?",":"",watch_iq[i][0],watch_iq[i][1]);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"]");
 if(telemetry_compact&&telemetry_full){unsigned k,j;wire_used=0;for(i=0;i<watch_iq_count;i++)for(j=0;j<2;j++)for(k=0;k<4;k++)wire_bytes[wire_used++]=(watch_iq[i][j]>>(k*8))&255;
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"watch_iq_codec\":\"le32-pairs-v1\",\"watch_iq_data\":\"");n+=wire_base64(snapshot+n,sizeof(snapshot)-n);n+=snprintf(snapshot+n,sizeof(snapshot)-n,"\"");}
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,",\"tdma\":{\"slot_us\":5000,\"slots\":20,\"cycle_us\":100000,\"max_model_samples\":%u,\"max_pl_cycles\":%u,\"max_arm_transaction_us\":%u,\"pl_service_overruns\":%u,\"arm_service_overruns\":%u}",tdma_max_samples,tdma_max_pl_cycles,tdma_max_arm_us,tdma_pl_overruns,tdma_arm_overruns);
 n=edge_report(n);
 n+=snprintf(snapshot+n,sizeof(snapshot)-n,"}");
 if(telemetry_overflow||n>=sizeof(snapshot)){reply("{\"ok\":0,\"error\":\"SNAPSHOT_OVERFLOW\"}");return;}reply("%s",snapshot);
}
static unsigned parse(const char*s){return (unsigned)strtoul(s,0,10);}
static int nib(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
int network_command(unsigned n,char**a){unsigned kind,offset,len,i,batch;uint8_t*target,*loaded;char hex[257];static char text[8192]; /* Single-thread command scratch, never recursive. */

 if(edge_command(n,a))return 1;
 if(!strcmp(a[0],"WALLIQ")&&n==1){
  unsigned pos=0,j,emitted=0;
  for(i=0;i<16;i++){
   WallCell *cell=&wall_cells[i];
   if(!cell->valid)continue;
   pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%u,%u,%u,\"",emitted++?",":"",i,cell->ms,cell->generation);
   wire_used=0;
   for(j=0;j<cell->count;j++){
    w32(wire_bytes+wire_used,cell->iq[j][0]);w32(wire_bytes+wire_used+4,cell->iq[j][1]);wire_used+=8;
   }
   pos+=wire_base64(text+pos,sizeof(text)-pos);
   pos+=snprintf(text+pos,sizeof(text)-pos,"\"]");
  }
  pos+=snprintf(text+pos,sizeof(text)-pos,"],\"tap_history\":[");
  for(i=0;i<tap_history_count;i++){
   const unsigned *point=tap_history[i];
   pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%u",i?",":"",point[0]);
   for(j=0;j<point[1];j++)pos+=snprintf(text+pos,sizeof(text)-pos,",%u",point[j+2]);
   pos+=snprintf(text+pos,sizeof(text)-pos,"]");
  }
  reply("{\"ok\":1,\"run_id\":%u,\"round\":%u,\"watch_link\":%u,\"cells\":[%s]}",run_id,round_index,watch_link,text);
  return 1;
 }
 if(!strcmp(a[0],"NETWATCH")&&n==2){char*e;unsigned v=strtoul(a[1],&e,10);if(!*a[1]||*e||v>=32){reply("{\"ok\":0,\"error\":\"LINK_RANGE\"}");return 1;}if(v!=watch_link){watch_iq_count=watch_iq_ms=watch_iq_generation=0;observation_valid=0;}watch_link=v;reply("{\"ok\":1,\"watch_link\":%u}",v);return 1;}

 if(!strcmp(a[0],"HBAUDIO")&&n==1){
  unsigned pos=0,j,node,count=0;
  pos+=snprintf(text+pos,sizeof(text)-pos,"{\"ok\":1,\"run_id\":%u,\"samples\":[",run_id);
  for(node=1;node<=16;node++)if(ground_audio_valid[node]){
   pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%u,%u,\"",count++?",":"",node,ground_seq[node]);
   for(j=0;j<48;j++)pos+=snprintf(text+pos,sizeof(text)-pos,"%02x",ground_audio[node][j]);
   pos+=snprintf(text+pos,sizeof(text)-pos,"\"]");
  }
  snprintf(text+pos,sizeof(text)-pos,"]}");reply("%s",text);return 1;
 }
 if(!strcmp(a[0],"HNSTATUS")&&n==1){unsigned pos=0,node,j;static const unsigned offsets[]={0x18,0x44,0x48,0x4c,0xa0,0x54,0x58,0x5c,0x50,0x64,0x60,0x88,0x68,0x6c,0x70,0x74,0x90,0x98};
  pos+=snprintf(text+pos,sizeof(text)-pos,"{\"ok\":1,\"source\":\"FPGA_HARDWARE_ENDPOINT_REGISTERS\",\"hardware_nodes\":[");
  for(node=9;node<=13;node+=4){unsigned base=hw_base(node);if(!hw_wait(node))return 1;pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%u",node==9?"":",",node);for(j=0;j<sizeof(offsets)/sizeof(offsets[0]);j++)pos+=snprintf(text+pos,sizeof(text)-pos,",%u",rd(base+offsets[j]));pos+=snprintf(text+pos,sizeof(text)-pos,"]");}
  snprintf(text+pos,sizeof(text)-pos,"],\"virtual_nodes\":[1,2,3,4,5,6,7,8,10,11,12,14,15,16],\"arm_business_proxy_for_hardware_nodes\":false}");reply("%s",text);return 1;
 }
 if(!strcmp(a[0],"HNENABLE")&&n==3){char *e1,*e2;unsigned node=(unsigned)strtoul(a[1],&e1,10),value=(unsigned)strtoul(a[2],&e2,10),base=hw_base(node);if(!base||value>1||!*a[1]||!*a[2]||*e1||*e2){reply("{\"ok\":0,\"error\":\"HARDWARE_NODE_RANGE\"}");return 1;}if(!hw_wait(node))return 1;hw_enabled[node==9?0:1]=value;wr(base+0x18,value);reply("{\"ok\":1,\"source\":\"HARDWARE_NODE_ENABLE\",\"node\":%u,\"enabled\":%u}",node,value);return 1;}
 if(!strcmp(a[0],"HNRESET")&&n==2){char *e;unsigned node=(unsigned)strtoul(a[1],&e,10),base=hw_base(node);if(!base||running||!*a[1]||*e){reply("{\"ok\":0,\"error\":\"RESET_REQUIRES_STOPPED_NETWORK\"}");return 1;}if(!hw_wait(node))return 1;queue_drops+=rd(base+0xa0);wr(base,16);reply("{\"ok\":1,\"node\":%u,\"reset_count\":%u}",node,rd(base+0x98));return 1;}



 if(!strcmp(a[0],"GCOMMAND")&&n==2){uint8_t b[96],payload[16];unsigned id,node,op,value,ttl,evict=64;GroundCommand*c;
  if(!running||strlen(a[1])!=40){reply("{\"ok\":0,\"error\":\"COMMAND_STATE_OR_LENGTH\"}");return 1;}
  for(i=0;i<40;i++)if(nib(a[1][i])<0){reply("{\"ok\":0,\"error\":\"HEX\"}");return 1;}
  for(i=0;i<20;i++){b[i]=nib(a[1][i*2])*16+nib(a[1][i*2+1]);}
  id=get_le32(b);node=get_le32(b+4);op=get_le32(b+8);value=get_le32(b+12);ttl=get_le32(b+16);
  if(!id||node<1||node>16||op<1||op>5||ttl<100||ttl>60000){reply("{\"ok\":0,\"error\":\"COMMAND_RANGE\"}");return 1;}
  if(op==5&&channel_configuration()[1]==1&&channel_configuration()[13]&&value<scene_terrain_minimum()){reply("{\"ok\":0,\"error\":\"TERRAIN_ALTITUDE_MIN\",\"minimum_m\":%u}",scene_terrain_minimum());return 1;}
  for(i=0;i<command_count;i++)if(commands[i].id==id){reply("{\"ok\":0,\"error\":\"COMMAND_ID_REUSED\"}");return 1;}
  if(id<=last_command_id){reply("{\"ok\":0,\"error\":\"COMMAND_ID_NOT_INCREASING\"}");return 1;}
  if(command_count==64){for(i=0;i<command_count;i++)if(round_index*100>commands[i].expiry_ms+60000){evict=i;break;}if(evict==64){reply("{\"ok\":0,\"error\":\"COMMAND_WINDOW_FULL_RETRY_LATER\"}");return 1;}}
  memset(payload,0,sizeof(payload));w32(payload,id);payload[4]=op;w32(payload+8,value);w32(payload+12,round_index*100+ttl);
  create_packet(b,0,6,generated_seq+1,0,1,(uint64_t)round_index*100000000,payload,16);b[5]=node;
  if(!enqueue(0,b)){reply("{\"ok\":0,\"error\":\"QUEUE_FULL\"}");return 1;}
  if(evict<64){memmove(commands+evict,commands+evict+1,(63-evict)*sizeof(commands[0]));command_count--;}last_command_id=id;c=&commands[command_count++];memset(c,0,sizeof(*c));c->id=id;c->target=node;c->opcode=op;c->value=value;c->expiry_ms=round_index*100+ttl;c->ground_status=1;
  generated_seq++;generated++;generated_by_type[6]++;reply("{\"ok\":1,\"type\":\"GCOMMAND\",\"command_id\":%u,\"status\":\"QUEUED_NOT_EXECUTED\"}",id);return 1;
 }
  if(!strcmp(a[0],"CMDSTATUS")&&n==1){unsigned pos=0;pos+=snprintf(text+pos,sizeof(text)-pos,"{\"ok\":1,\"source\":\"GROUND_RECEIVED_COMMAND_RESULTS\",\"commands\":[");for(i=0;i<command_count;i++){GroundCommand*c=&commands[i];unsigned status=c->ground_status;if(status==1&&round_index*100>c->expiry_ms+60000)status=5;pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%u,%u,%u,%u,%u,%u,%u,%u,%u,%u]",i?",":"",c->id,c->target,c->opcode,c->value,status,c->ground_received_ms,c->expiry_ms,c->ground_period,c->ground_pause,c->ground_rate);}snprintf(text+pos,sizeof(text)-pos,"]}");reply("%s",text);return 1;}
  if(!strcmp(a[0],"GACKDROP")&&n==2&&running){unsigned id=parse(a[1]);for(i=0;i<command_count;i++)if(commands[i].id==id)break;if(i==command_count){reply("{\"ok\":0,\"error\":\"UNKNOWN_COMMAND\"}");return 1;}command_ack_drop=id;reply("{\"ok\":1,\"source\":\"TEST_ONE_FINAL_HOP_ACK_DISABLED_IN_PL\"}");return 1;}
  if(!strcmp(a[0],"CMDTRACE")&&n==1){unsigned pos=0,j;pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"{\"ok\":1,\"source\":\"ARM_DIAGNOSTIC_OF_PL_TRANSACTIONS_NOT_GROUND_ACK\",\"executions\":[");for(i=0;i<command_count;i++)pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"%s[%u,%u]",i?",":"",commands[i].id,commands[i].executions);pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"],\"limit\":256,\"hops\":[");for(i=0;i<command_trace_count;i++){pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"%s[",i?",":"");for(j=0;j<10;j++)pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"%s%u",j?",":"",command_trace[i][j]);pos+=snprintf(snapshot+pos,sizeof(snapshot)-pos,"]");}snprintf(snapshot+pos,sizeof(snapshot)-pos,"]}");reply("%s",snapshot);return 1;}
 if(!strcmp(a[0],"EXTINJECT")&&n==4){uint8_t payload[64],b[96];unsigned node=parse(a[1]),kind=parse(a[2]),size=strlen(a[3]),k;int32_t xyz[3];
  for(k=1;k<=2;k++){char*e;unsigned long v=strtoul(a[k],&e,10);if(!*a[k]||*e||*a[k]=='-'||v>0xffffffffUL){reply("{\"ok\":0,\"error\":\"NUMBER\"}");return 1;}}
  if(!running||!node||node>16||node!=(unsigned)scene_configuration()[14]||(kind!=1&&kind!=2&&kind!=5)||!size||size>128||(size&1)||(kind==1&&size!=32)){reply("{\"ok\":0,\"error\":\"EXTERNAL_RANGE_OR_STATE\"}");return 1;}
  for(i=0;i<size;i++)if(nib(a[3][i])<0){reply("{\"ok\":0,\"error\":\"HEX\"}");return 1;}
  for(i=0;i<size/2;i++)payload[i]=nib(a[3][i*2])*16+nib(a[3][i*2+1]);
  if(kind==1){for(i=0;i<3;i++)xyz[i]=(int32_t)get_le32(payload+i*4);if(channel_configuration()[1]==1&&channel_configuration()[13]&&xyz[2]<(int32_t)(scene_terrain_minimum()*1000)){reply("{\"ok\":0,\"error\":\"TERRAIN_ALTITUDE_MIN\",\"minimum_m\":%u}",scene_terrain_minimum());return 1;}if(xyz[0]<0||xyz[0]>10000000||xyz[1]<0||xyz[1]>10000000||xyz[2]<50000||xyz[2]>900000){reply("{\"ok\":0,\"error\":\"EXTERNAL_POSITION\"}");return 1;}}
  create_packet(b,node,kind,generated_seq+1,0,1,(uint64_t)round_index*100000000,payload,size/2);b[2]=1;
  if(!enqueue(node,b)){reply("{\"ok\":0,\"error\":\"QUEUE_FULL\"}");return 1;}
  if(kind==1)scene_external_position(node,xyz,round_index*.1);
  generated_seq++;generated++;generated_by_type[kind]++;external_injected++;if(kind==5)load_generated++;
  reply("{\"ok\":1,\"type\":\"EXTINJECT\",\"source\":\"EXTERNAL_INGRESS_QUEUED\",\"sequence\":%u,\"model_ms\":%u}",generated_seq,round_index*100);return 1;
 }
 if(!strcmp(a[0],"EXTRX")&&n==1){if(!external_received_valid){reply("{\"ok\":0,\"error\":\"NO_RECEIVED_EXTERNAL_FRAME\"}");return 1;}for(i=0;i<96;i++)sprintf(hex+2*i,"%02x",external_received[i]);reply("{\"ok\":1,\"source\":\"FPGA_RX_GROUND_REASSEMBLY\",\"frame_hex\":\"%s\",\"injected\":%u}",hex,external_injected);return 1;}
 if(!strcmp(a[0],"SCENERUNTIME")&&n==1){scene_runtime_json(text,sizeof(text));reply("{\"ok\":1,\"run_id\":%u,\"model_ms\":%u,\"runtime\":%s}",run_id,round_index*100,text);return 1;}
 if(!strcmp(a[0],"SCENECFG")&&n==2){unsigned err=running?4:scene_configure(a[1]);if(!err)channel_reset();reply("{\"ok\":%u,\"type\":\"SCENECFG\",\"error_code\":%u,\"config_id\":%u}",err?0:1,err,scene_config_id());return 1;}
 if(!strcmp(a[0],"CHANNELCFG")&&n==2){unsigned e=running?6:channel_configure(a[1]);reply("{\"ok\":%u,\"error_code\":%u,\"channel_id\":%u}",e?0:1,e,channel_config_id());return 1;}
 if(!strcmp(a[0],"CHANNELINFO")&&n==1){unsigned j,z=0;const int32_t*v=channel_configuration();z+=snprintf(text+z,sizeof(text)-z,"{\"ok\":1,\"channel_id\":%u,\"values\":[",channel_config_id());for(j=0;j<48;j++)z+=snprintf(text+z,sizeof(text)-z,"%s%d",j?",":"",v[j]);snprintf(text+z,sizeof(text)-z,"]}");reply("%s",text);return 1;}
 if(!strcmp(a[0],"CHFRAME")&&n==4){unsigned j,z=0,id=parse(a[1]),ms=parse(a[2]),seed=parse(a[3]);LinkConfig base;ChannelFrame f;
  if(id>=32||!seed){reply("{\"ok\":0,\"error\":\"CHANNEL_QUERY_RANGE\"}");return 1;}
  scene_link(id,ms/1000.,seed,&base);channel_frame(id,ms/1000.,seed,&base,&f);
  z+=snprintf(text+z,sizeof(text)-z,"{\"ok\":1,\"channel_id\":%u,\"sample_rate_hz\":%.0f,\"loss_db\":%.8f,\"rain_db_km\":%.8f,\"limited\":%u,\"taps\":[",channel_config_id(),f.fs,f.loss_db,f.rain_db_km,f.clamped);
  for(j=0;j<f.count;j++){ChannelTap*p=&f.taps[j];z+=snprintf(text+z,sizeof(text)-z,"%s[%.8f,%.8f,%.8f,%.8f,%.8f,%u]",j?",":"",p->gain,p->delay,p->phase,p->cfo,p->ramp_per_second,p->reflections);}
  z+=snprintf(text+z,sizeof(text)-z,"],\"digital_scale\":%.12f,\"terrain\":[",channel_digital_scale(&f,base.sigma));
  for(j=0;j<7;j++)z+=snprintf(text+z,sizeof(text)-z,"%s%.8f",j?",":"",f.terrain[j]);
  snprintf(text+z,sizeof(text)-z,"]}");reply("%s",text);return 1;
 }
 if(!strcmp(a[0],"SCENEINFO")&&n==1){const int32_t*c=scene_configuration();reply("{\"ok\":1,\"schema\":1,\"config_id\":%u,\"values\":[%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d]}",scene_config_id(),c[0],c[1],c[2],c[3],c[4],c[5],c[6],c[7],c[8],c[9],c[10],c[11],c[12],c[13],c[14],c[15]);return 1;}
 if(!strncmp(a[0],"NET",3)||!strncmp(a[0],"MEDIA",5)||!strcmp(a[0],"SCENE")){
  for(i=1;i<n;i++){char *end;unsigned long long value;if(!strcmp(a[0],"MEDIASET")&&i==3)continue;value=strtoull(a[i],&end,10);if(!*a[i]||*a[i]=='-'||*end||value>0xffffffffULL){reply("{\"ok\":0,\"error\":\"NUMBER\"}");return 1;}}
  if(!strcmp(a[0],"SCENE")&&n==3){LinkConfig c;unsigned link=parse(a[1]);double t=parse(a[2])/1000.;if(link>=32){reply("{\"ok\":0,\"error\":\"LINK\"}");return 1;}scene_link(link,t,20261009,&c);reply("{\"ok\":1,\"type\":\"SCENE\",\"distance_mm\":%u,\"cfo_millihz\":%d,\"gain0_q15\":%u,\"gain1_q15\":%u,\"sigma\":%u,\"delay_samples\":%u,\"seed\":%u}",(unsigned)llround(c.distance*1000),(int)llround(c.cfo*1000),bounded_gain(c.gain0),bounded_gain(c.gain1),(unsigned)llround(c.sigma),(unsigned)llround(c.delay),c.seed);return 1;}
  if(!strcmp(a[0],"NETFEC")&&n==2&&!running){unsigned mode=parse(a[1]);if(mode>1){reply("{\"ok\":0,\"error\":\"FEC_RANGE\"}");return 1;}fec_enabled=mode;reply("{\"ok\":1,\"fec\":%u}",fec_enabled);return 1;}
  if(!strcmp(a[0],"NETLOAD")&&n==2){unsigned rate=parse(a[1]);if(rate>100){reply("{\"ok\":0,\"error\":\"LOAD_RANGE\"}");return 1;}load_pps=rate;reply("{\"ok\":1,\"load_pps_per_source\":%u}",load_pps);return 1;}
  if(!strcmp(a[0],"NETSTART")&&n==4&&!running){duration=parse(a[1]);master_seed=parse(a[2]);ideal=parse(a[3]);if(duration>604800||!master_seed||ideal>1){reply("{\"ok\":0,\"error\":\"RANGE\"}");return 1;}
    media_sequence[0]=0x70000001;media_sequence[1]=0x70000002;memset(media_total_rx,0,sizeof(media_total_rx));memset(media_total_tx,0,sizeof(media_total_tx));edge_reset();last_command_id=0;command_count=command_trace_count=command_ack_drop=0;memset(commands,0,sizeof(commands));for(i=0;i<17;i++){heartbeat_rounds[i]=10;media_paused[i]=0;media_rate[i]=5;}scene_runtime_reset();external_received_valid=external_injected=0;memset(external_received,0,sizeof(external_received));memset(delay_hist,0,sizeof(delay_hist));memset(generated_by_type,0,sizeof(generated_by_type));memset(received_by_type,0,sizeof(received_by_type));memset(timely_by_type,0,sizeof(timely_by_type));timely_delivered=late_delivered=loss_expired=loss_attempt_limit=0;telemetry_compact=0;telemetry_full=1;
   load_generated=load_delivered=load_bytes=load_accum=0;
   for(i=0;i<audio_len;i++)if(!audio_load[i]){reply("{\"ok\":0,\"error\":\"AUDIO_INCOMPLETE\"}");return 1;}
   for(i=0;i<video_len;i++)if(!video_load[i]){reply("{\"ok\":0,\"error\":\"VIDEO_INCOMPLETE\"}");return 1;}
   memset(queues,0,sizeof(queues));seen_reset();memset(stats,0,sizeof(stats));memset(applied,0,sizeof(applied));memset(phy_snapshot,0,sizeof(phy_snapshot));watch_iq_count=watch_iq_ms=watch_iq_generation=0;memset(audio_rx,0,sizeof(audio_rx));memset(video_rx,0,sizeof(video_rx));memset(audio_map,0,sizeof(audio_map));memset(video_map,0,sizeof(video_map));memset(ground_seq,0,sizeof(ground_seq));memset(ground_seen_ms,0,sizeof(ground_seen_ms));memset(ground_updates,0,sizeof(ground_updates));memset(ground_audio_valid,0,sizeof(ground_audio_valid));memset(observed,0,sizeof(observed));memset(ground_generated_ms,0,sizeof(ground_generated_ms));memset(alarm_events,0,sizeof(alarm_events));alarm_count=0;fatal_code=0;
   for(i=0;i<32;i++){random_state[i]=scene_seed(master_seed,i,"fast");}run_id=scene_seed(master_seed,duration,ideal?"ideal_run":"run");tdma_max_samples=tdma_max_pl_cycles=tdma_max_arm_us=tdma_pl_overruns=tdma_arm_overruns=0;round_index=generated=delivered=ground_bytes=queue_drops=retry_drops=generated_seq=queue_peak=slot_misses=audio_next=video_next=audio_received=video_received=delivered_hb=delivered_alarm=0;e2e_delay_ns=e2e_max_ns=0;running=1;hw_init();if(fatal_code){reply("{\"ok\":0,\"error\":\"HARDWARE_NODE_INIT\"}");return 1;}XTime_GetTime(&run_start);reply("{\"ok\":1,\"type\":\"NETSTART\",\"run_id\":%u}",run_id);return 1;
  }
  if((!strcmp(a[0],"NETSTEP")||!strcmp(a[0],"NETTICK")||!strcmp(a[0],"NETFAST"))&&n==2&&running){telemetry_compact=1;telemetry_full=!strcmp(a[0],"NETFAST")?2:!strcmp(a[0],"NETSTEP");batch=parse(a[1]);if(!batch||batch>200){reply("{\"ok\":0,\"error\":\"BATCH\"}");return 1;}tap_history_count=0;edge_trace_count=edge_trace_overflow=0;while(batch--&&running){unsigned slot;generate(round_index);for(slot=0;slot<20&&running;slot++){uint64_t ns=(uint64_t)round_index*100000000+(uint64_t)slot*5000000;if(slot<16)attempt(slot+1,ns,0);else if(slot==16&&choose(0,0))attempt(0,ns,0);else {unsigned j;for(j=0;j<4;j++){unsigned node=(slot-16)*4+j+1;if(hw_base(node)?hw_choose(node,1):(choose(node,1)!=0)){attempt(node,ns,1);break;}}}}round_index++;if(duration&&round_index>=duration*10)running=0;if(round_index>=40000000U){fatal_code=231;running=0;}}report();return 1;}
  if(!strcmp(a[0],"NETACKDROP")&&n==2&&!running){ack_drop_once=parse(a[1]);if(ack_drop_once>1){ack_drop_once=0;reply("{\"ok\":0,\"error\":\"RANGE\"}");}else reply("{\"ok\":1,\"type\":\"NETACKDROP\"}");return 1;}
  if(!strcmp(a[0],"NETSTATUS")&&n==1){telemetry_compact=0;telemetry_full=1;report();return 1;}
  if(!strcmp(a[0],"NETSTOP")&&n==1){running=0;sw_payload_abort();reply("{\"ok\":1,\"type\":\"NETSTOP\"}");return 1;}
  if(!strcmp(a[0],"MEDIAADVANCE")&&n==3&&running){unsigned seq;kind=parse(a[1]);seq=parse(a[2]);
   if((kind!=3&&kind!=4)||seq!=media_sequence[kind-3]){reply("{\"ok\":0,\"error\":\"MEDIA_OBJECT_CHANGED\"}");return 1;}
   len=kind==3?audio_len:video_len;
   if(!len||(kind==3?audio_next:video_next)!=(len+63)/64||media_pending(kind,seq)){reply("{\"ok\":0,\"error\":\"MEDIA_OBJECT_IN_FLIGHT\"}");return 1;}
   if(seq>=0x7ffffffdU){reply("{\"ok\":0,\"error\":\"MEDIA_ID_EXHAUSTED\"}");return 1;}
   media_sequence[kind-3]+=2;
   if(kind==3){audio_next=audio_received=0;memset(audio_map,0,sizeof(audio_map));memset(audio_rx,0,sizeof(audio_rx));}
   else{video_next=video_received=0;memset(video_map,0,sizeof(video_map));memset(video_rx,0,sizeof(video_rx));}
   reply("{\"ok\":1,\"kind\":%u,\"object_id\":%u}",kind,media_sequence[kind-3]);return 1;
  }
  if(!strcmp(a[0],"MEDIACLEAR")&&n==3&&!running){audio_len=parse(a[1]);video_len=parse(a[2]);if(audio_len>AUDIO_MAX||video_len>VIDEO_MAX){audio_len=video_len=0;reply("{\"ok\":0,\"error\":\"MEDIA_SIZE\"}");return 1;}memset(audio_load,0,sizeof(audio_load));memset(video_load,0,sizeof(video_load));reply("{\"ok\":1,\"type\":\"MEDIACLEAR\"}");return 1;}
  if(!strcmp(a[0],"MEDIASET")&&n==4&&!running){kind=parse(a[1]);offset=parse(a[2]);len=strlen(a[3]);target=kind==3?audio_tx:video_tx;loaded=kind==3?audio_load:video_load;if((kind!=3&&kind!=4)||!len||(len&1)||len>384||offset> (kind==3?audio_len:video_len)||len/2>(kind==3?audio_len:video_len)-offset){reply("{\"ok\":0,\"error\":\"MEDIA_RANGE\"}");return 1;}for(i=0;i<len;i++)if(nib(a[3][i])<0){reply("{\"ok\":0,\"error\":\"HEX\"}");return 1;}for(i=0;i<len/2;i++){target[offset+i]=nib(a[3][i*2])*16+nib(a[3][i*2+1]);loaded[offset+i]=1;}reply("{\"ok\":1,\"type\":\"MEDIASET\"}");return 1;}
  if(!strcmp(a[0],"MEDIAGET")&&((n==4&&!running)||n==5)){kind=parse(a[1]);offset=parse(a[2]);len=parse(a[3]);target=kind==3?audio_rx:video_rx;if(n==5&&((kind!=3&&kind!=4)||parse(a[4])!=media_sequence[kind-3])){reply("{\"ok\":0,\"error\":\"MEDIA_OBJECT_CHANGED\"}");return 1;}if((kind!=3&&kind!=4)||!len||len>128||offset>(kind==3?audio_len:video_len)||len>(kind==3?audio_len:video_len)-offset){reply("{\"ok\":0,\"error\":\"MEDIA_RANGE\"}");return 1;}for(i=0;i<len;i++){unsigned idx=(offset+i)/64;if(!(kind==3?audio_map[idx]:video_map[idx])){reply("{\"ok\":0,\"error\":\"MISSING_RECEIVED_FRAGMENT\"}");return 1;}sprintf(hex+2*i,"%02x",target[offset+i]);}reply("{\"ok\":1,\"type\":\"MEDIAGET\",\"hex\":\"%s\"}",hex);return 1;}
  reply("{\"ok\":0,\"error\":\"NETWORK_COMMAND_OR_STATE\"}");return 1;
 }return 0;
}
