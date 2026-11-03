#include "payload_driver.h"
#include "xil_io.h"
#include "xtime_l.h"
static unsigned rd(unsigned o){return Xil_In32(SWARM_BASE+o);}
static void wr(unsigned o,unsigned v){Xil_Out32(SWARM_BASE+o,v);}
static void barrier(void){__asm__ volatile("dmb sy" ::: "memory");}
unsigned sw_payload_prepare(const unsigned char *b,unsigned len,unsigned tag){unsigned i,w,s=rd(SW_STATUS);if(s&1)return SW_EBUSY;if(s&2)return SW_EPENDING;
 if(!b||len<1||len>64)return SW_ELENGTH;
 wr(SW_CONTROL,16);wr(0x304,0);wr(SW_TX_LEN,len);wr(SW_TAG,tag);
 for(i=0;i<96;i+=4){w=(unsigned)b[i]|((unsigned)b[i+1]<<8)|((unsigned)b[i+2]<<16)|((unsigned)b[i+3]<<24);wr(SW_TX_BUFFER+i,w);}barrier();return rd(SW_LAST_ERROR);
}
unsigned sw_payload_start(void){wr(SW_CONTROL,16);barrier();wr(SW_CONTROL,1);barrier();return rd(SW_LAST_ERROR);}
int sw_payload_wait(unsigned timeout_ms){XTime begin,now;XTime_GetTime(&begin);do {if(rd(SW_STATUS)&2)return 1;XTime_GetTime(&now);}while(now-begin<((XTime)COUNTS_PER_SECOND*timeout_ms)/1000);sw_payload_abort();return 0;}
unsigned sw_payload_read(unsigned char *b){unsigned i,w,s=rd(SW_STATUS);if(s&1)return SW_EBUSY;if((s&6)!=6||!b)return SW_ENORESULT;
 for(i=0;i<96;i+=4){w=rd(SW_RX_BUFFER+i);b[i]=w;b[i+1]=w>>8;b[i+2]=w>>16;b[i+3]=w>>24;}barrier();return SW_EOK;
}
unsigned sw_payload_release(void){wr(SW_CONTROL,16);wr(SW_CONTROL,4);barrier();return rd(SW_LAST_ERROR);}
void sw_payload_abort(void){wr(SW_CONTROL,8);barrier();}
