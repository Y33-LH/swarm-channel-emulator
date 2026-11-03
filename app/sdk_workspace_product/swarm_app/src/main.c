#include "payload_driver.h"
#include "network.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_mmu.h"
#include "xparameters.h"
#include "xuartps_hw.h"
#include "xuartps.h"
#include "xtime_l.h"
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#define BASE 0x43C00000U
#define VERSION 0x000d0004U
#define PROTOCOL 20
static unsigned rd(unsigned o){return Xil_In32(BASE+o);}
static void wr(unsigned o,unsigned v){Xil_Out32(BASE+o,v);}
#include "transport.h"
void reply(const char *format,...){
 static char text[32768];va_list ap;unsigned n;int written;
 va_start(ap,format);written=vsnprintf(text,sizeof(text),format,ap);va_end(ap);
 if(written<0||(unsigned)written>=sizeof(text))strcpy(text,"{\"ok\":0,\"error\":\"RESPONSE_OVERFLOW\"}");
 n=strlen(text);
 if(transport_active){memcpy(transport_cache,text,n+1);transport_length=n;transport_valid=1;transport_send(transport_id,text,n);}
 else {uart_text(text,n);uart_text("\r\n",2);}
}
#include "runtime_memory.h"
static void fail(const char *s,unsigned code){reply("{\"ok\":0,\"error\":\"%s\",\"code\":%u}",s,code);}
static int number(const char *s,unsigned *v){unsigned n=0,d;if(!*s)return 0;while(*s){if(*s<'0'||*s>'9')return 0;d=*s++-'0';if(n>429496729U||(n==429496729U&&d>5))return 0;n=n*10+d;}*v=n;return 1;}
static int nibble(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
static int decode_hex(const char *s,unsigned char *b,unsigned cap){unsigned n=strlen(s),i;int a,c;if(!n||(n&1)||n>cap*2)return -1;for(i=0;i<n/2;i++){a=nibble(s[2*i]);c=nibble(s[2*i+1]);if(a<0||c<0)return -1;b[i]=(a<<4)|c;}return n/2;}
static void hex_encode(const unsigned char *b,unsigned n,char *s){static const char h[]="0123456789abcdef";unsigned i;for(i=0;i<n;i++){s[i*2]=h[b[i]>>4];s[i*2+1]=h[b[i]&15];}s[n*2]=0;}
static uint16_t crc16(const unsigned char *b,unsigned n){uint16_t c=0xffff;unsigned i,j;for(i=0;i<n;i++){c^=(uint16_t)b[i]<<8;for(j=0;j<8;j++)c=(c&0x8000)?(c<<1)^0x1021:c<<1;}return c;}
static void make_frame(unsigned char *b,const unsigned char *data,unsigned len,unsigned tag){
 memset(b,0,96);b[0]=1;b[1]=1;b[3]=1;b[4]=1;b[6]=1;b[8]=0x13;b[18]=1;
 b[12]=tag;b[13]=tag>>8;b[14]=tag>>16;b[15]=tag>>24;b[28]=len;b[29]=len>>8;memcpy(b+32,data,len);
}
#define prepare sw_payload_prepare
#define start_frame sw_payload_start
#define wait_done() sw_payload_wait(3000)
#define read_frame(b) sw_payload_read(b)
static void result(void){unsigned char b[96];char h[193];unsigned s=rd(0x10),code=rd(0x14),len=rd(0x18),crcs=rd(0x4c);
 if(!(s&2)){fail((s&1)?"BUSY":"NO_RESULT",(s&1)?1:9);return;}
 h[0]=0;if(s&4)read_frame(b);if(s&4)hex_encode(b,96,h);
 reply("{\"ok\":%u,\"type\":\"RESULT\",\"version\":%u,\"status\":%u,\"result_code\":%u,\"rx_len\":%u,\"rx_frame_bytes\":%u,\"tag\":%u,\"generation\":%u,\"tx_bits\":%u,\"rx_bits\":%u,\"cycles\":%u,\"crc_calc\":%u,\"crc_recv\":%u,\"last_error\":%u,\"rx_hex\":\"%s\"}",((s&4)&&!code)?1:0,VERSION,s,code,len,rd(0x1c),rd(0x38),rd(0x2c),rd(0x20),rd(0x24),rd(0x28),crcs&65535,crcs>>16,rd(0x34),h);
}
static void ideal_reset(void){unsigned o;wr(0,4);wr(12,0);wr(48,5000000);wr(64,32768);wr(68,0);for(o=80;o<=96;o+=4)wr(o,o==88?1:0);for(o=112;o<=140;o+=4)wr(o,0);wr(192,0);wr(0x304,0);}
static void selftest(unsigned count){unsigned char data[64],tx[96],rx[96];unsigned k,i,len,rng=0x12345678,code,firstgen=rd(0x2c);uint16_t c;
 if(rd(0x10)&1){fail("BUSY",1);return;}
 ideal_reset();
 for(k=0;k<count;k++){
  wr(0,4);wr(0x40,32768);wr(0x44,0);wr(0xc,0);wr(0x30,5000000);len=(k%64)+1;
  for(i=0;i<len;i++){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;data[i]=(k%4==0)?0:(k%4==1)?255:(k%4==2)?((i&1)?0x55:0xaa):(rng&255);}
  make_frame(tx,data,len,k+1);code=prepare(tx,len,k+1);if(!code)code=start_frame();
  if(code||!wait_done()||!(rd(0x10)&4)){reply("{\"ok\":0,\"type\":\"SELFTEST\",\"failed_index\":%u,\"driver_error\":%u,\"result_code\":%u}",k,code,rd(0x14));return;}
  read_frame(rx);c=crc16(tx,96);
  if(memcmp(tx,rx,96)||rd(0x18)!=len||rd(0x1c)!=96||rd(0x20)!=784||rd(0x24)!=784||rd(0x4c)!=((unsigned)c<<16|c)){
   reply("{\"ok\":0,\"type\":\"SELFTEST\",\"failed_index\":%u,\"error\":\"DATA_MISMATCH\"}",k);return;}
 }
 reply("{\"ok\":1,\"type\":\"SELFTEST\",\"passed\":%u,\"bytes_compared\":%u,\"generation_delta\":%u}",count,count*96,rd(0x2c)-firstgen);
}
static void command(char *line){char *t[5],*s;unsigned n=0,a,b,code;int length;unsigned char data[96],frame[96];
 for(s=strtok(line," \t");s;s=strtok(0," \t")){if(n==5){fail("ARGUMENTS",0);return;}t[n++]=s;}if(!n){fail("EMPTY",0);return;}
 if(!strcmp(t[0],"MEMORY")&&n==1){memory_report();return;}
 if(network_command(n,t))return;
 if(!strcmp(t[0],"PHYSTATS")&&n==1){
  reply("{\"ok\":1,\"type\":\"PHYSTATS\",\"version\":%u,\"fec_mode\":%u,\"cfo_phase_step\":%d,\"channel_i\":%d,\"channel_q\":%d,\"omega_q16\":%d,\"timing_updates\":%u,\"pre_errors\":%u,\"pre_bits\":%u,\"post_errors\":%u,\"post_bits\":%u,\"decode_cycles\":%u,\"turbo_iterations\":%u,\"evm_error_sum\":%llu,\"evm_symbols\":%u,\"iq_count\":%u}",rd(60),rd(192),(int)rd(196),(int)rd(200),(int)rd(204),(int)rd(208),rd(212),rd(216),rd(220),rd(160),rd(164),rd(224),rd(228),(unsigned long long)(rd(232)|((uint64_t)rd(236)<<32)),rd(240),rd(768));return;
 }
 if(!strcmp(t[0],"IQ")&&n==4){unsigned offset,count,bank,j;char text[1600];unsigned pos=0;
  if(!number(t[1],&offset)||!number(t[2],&count)||!number(t[3],&bank)||bank>1||count<1||count>64||offset>=512||count>512-offset||offset+count>rd(768)||(rd(16)&1)){fail("IQ_RANGE_OR_BUSY",10);return;}
  wr(248,bank);pos+=snprintf(text+pos,sizeof(text)-pos,"{\"ok\":1,\"type\":\"IQ\",\"source\":\"FPGA_SAMPLE_RAM\",\"offset\":%u,\"equalized\":%u,\"generation\":%u,\"iq\":[",offset,bank,rd(44));
  for(j=0;j<count;j++){wr(244,offset+j);a=rd(252);pos+=snprintf(text+pos,sizeof(text)-pos,"%s[%d,%d]",j?",":"",(int)(int16_t)(a&65535),(int)(int16_t)(a>>16));}
  snprintf(text+pos,sizeof(text)-pos,"]}");reply("%s",text);return;
 }
 if(!strcmp(t[0],"PING")&&n==1){reply("{\"ok\":1,\"type\":\"PING\",\"protocol\":20,\"transport\":\"crc32-replay-v1\",\"intervention_schema\":1,\"arm_build\":\"20261101-observation2\",\"baud\":230400,\"version\":%u,\"pl_hz\":62500000,\"body_bytes\":96,\"max_payload\":64}",rd(0x3c));return;}
 if(!strcmp(t[0],"STATUS")&&n==1){reply("{\"ok\":1,\"type\":\"STATUS\",\"status\":%u,\"last_error\":%u,\"generation\":%u,\"gain_q15\":%u,\"sigma\":%u}",rd(0x10),rd(0x34),rd(0x2c),rd(0x40),rd(0x44));return;}
 if(!strcmp(t[0],"RESULT")&&n==1){result();return;}
 if(!strcmp(t[0],"ABORT")&&n==1){wr(0,8);reply("{\"ok\":1,\"type\":\"ABORT\"}");return;}
 if(!strcmp(t[0],"RELEASE")&&n==1){wr(0,16);wr(0,4);code=rd(0x34);reply("{\"ok\":%u,\"type\":\"RELEASE\",\"code\":%u}",code?0:1,code);return;}
 if(!strcmp(t[0],"START")&&n==1){code=start_frame();reply("{\"ok\":%u,\"type\":\"START\",\"code\":%u}",code?0:1,code);return;}
 if(!strcmp(t[0],"ABORTTEST")&&n==1){XTime begin,now;unsigned partial;
  if(rd(0x10)&1){fail("BUSY",1);return;}
  ideal_reset();
  memset(data,0xa5,64);make_frame(frame,data,64,99999);code=prepare(frame,64,99999);if(!code)code=start_frame();
  XTime_GetTime(&begin);do {partial=rd(0x24);XTime_GetTime(&now);}while(partial<256&&now-begin<COUNTS_PER_SECOND);
  sw_payload_abort();
  reply("{\"ok\":%u,\"type\":\"ABORTTEST\",\"rx_bits_before_abort\":%u,\"status\":%u,\"result_code\":%u,\"rx_len\":%u}",(!code&&partial>=256&&partial<784&&rd(0x14)==3&&rd(0x18)==0)?1:0,partial,rd(0x10),rd(0x14),rd(0x18));return;
 }
 if(!strcmp(t[0],"SELFTEST")&&n==2){if(!number(t[1],&a)||a<1||a>10000){fail("RANGE",0);return;}selftest(a);return;}
 if((!strcmp(t[0],"SEND")||!strcmp(t[0],"LOAD"))&&n==3){
  if(!number(t[1],&a)){fail("TAG",0);return;}length=decode_hex(t[2],data,!strcmp(t[0],"SEND")?64:96);
  if(length<1||(!strcmp(t[0],"LOAD")&&length!=96)){fail("HEX_LENGTH",0);return;}
  if(!strcmp(t[0],"SEND")){make_frame(frame,data,length,a);code=prepare(frame,length,a);if(!code)code=start_frame();}
  else {length=data[28]|((unsigned)data[29]<<8);code=prepare(data,length,a);}
  reply("{\"ok\":%u,\"type\":\"%s\",\"code\":%u,\"tag\":%u}",code?0:1,t[0],code,a);return;
 }
 if(!strcmp(t[0],"READ")&&n==2){if(!number(t[1],&a)||a>4092||(a&3)){fail("ADDRESS",8);return;}b=rd(a);reply("{\"ok\":1,\"type\":\"READ\",\"offset\":%u,\"value\":%u,\"last_error\":%u}",a,b,rd(0x34));return;}
 if(!strcmp(t[0],"WRITE")&&n==3){if(!number(t[1],&a)||!number(t[2],&b)||a>4092||(a&3)){fail("ARGUMENTS",8);return;}wr(0,16);wr(a,b);code=rd(0x34);reply("{\"ok\":%u,\"type\":\"WRITE\",\"code\":%u}",code?0:1,code);return;}
 fail("COMMAND_OR_ARGUMENTS",0);
}
static void dispatch(char *line){
 char *s,*body,*end;unsigned id,expected;unsigned long v;
 transport_active=0;
 if(strncmp(line,"Q ",2)){command(line);return;}
 s=line+2;v=strtoul(s,&end,10);
 if(end==s||*end!=' '||!v||*s=='-'){fail("TRANSPORT_HEADER",0);return;}id=(unsigned)v;s=end+1;
 v=strtoul(s,&end,16);if(end==s||*end!=' '||(unsigned)(end-s)!=8){transport_error(id,"HEADER");return;}expected=(unsigned)v;body=end+1;
 if(!*body||strlen(body)>=sizeof(transport_command)||transport_crc(body,strlen(body))!=expected){transport_error(id,"REQUEST_CRC");return;}
 if(transport_valid&&id==transport_id){
  if(strcmp(body,transport_command)){transport_error(id,"REQUEST_ID_REUSED");return;}
  transport_send(transport_id,transport_cache,transport_length);return;
 }
 strcpy(transport_command,body);transport_id=id;transport_valid=0;transport_active=1;
 command(body);transport_active=0;
}
int main(void){static char line[512];unsigned used=0,overflow=0;char c;
 // DDR queues are ARM-owned (no DMA); PL registers/buffers remain strongly
 // ordered and uncached. Caching ordinary DDR cannot fabricate RX MMIO data.
 Xil_SetTlbAttributes(BASE,STRONG_ORDERED);
 Xil_ICacheEnable(); Xil_DCacheEnable();
 memory_init();
 {XUartPs uart;XUartPs_Config *cfg=XUartPs_LookupConfig(XPAR_XUARTPS_0_DEVICE_ID);
  if(!cfg||XUartPs_CfgInitialize(&uart,cfg,cfg->BaseAddress)!=XST_SUCCESS)return 2;
  if(XUartPs_SetBaudRate(&uart,230400)!=XST_SUCCESS)return 3;
 }
 if(rd(0x3c)!=VERSION){fail("WRONG_PL_VERSION",rd(0x3c));return 1;}
 reply("{\"ok\":1,\"type\":\"READY\",\"protocol\":20}");
 for(;;){
  if(!XUartPs_IsReceiveData(STDIN_BASEADDRESS))continue;
  c=(char)XUartPs_ReadReg(STDIN_BASEADDRESS,XUARTPS_FIFO_OFFSET);
  if(c=='\r')continue;
  if(c=='\n'){if(overflow)fail("LINE_TOO_LONG",0);else {line[used]=0;dispatch(line);}used=0;overflow=0;}
  else if(used<sizeof(line)-1&&!overflow)line[used++]=c;else overflow=1;
 }
}
