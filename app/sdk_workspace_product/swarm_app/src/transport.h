/* CRC-protected stop-and-wait RPC. A duplicate request returns the exact cached
 * reply, never executes NETSTEP/START/commands twice. Legacy commands remain
 * available for recovery and capability discovery. CRC is integrity, not auth. */
#ifndef SWARM_TRANSPORT_H
#define SWARM_TRANSPORT_H
static uint32_t transport_crc(const char *data,unsigned n){
 uint32_t c=0xffffffffU;unsigned i,k;
 for(i=0;i<n;i++){c^=(unsigned char)data[i];for(k=0;k<8;k++)c=(c>>1)^((0U-(c&1U))&0xedb88320U);}
 return c^0xffffffffU;
}
static char transport_cache[32768],transport_command[512];
static unsigned transport_id,transport_length,transport_valid,transport_active;
static void uart_text(const char *p,unsigned n){unsigned i;for(i=0;i<n;i++)XUartPs_SendByte(STDOUT_BASEADDRESS,p[i]);}
static void transport_send(unsigned id,const char *text,unsigned n){
 char prefix[80];unsigned k=(unsigned)snprintf(prefix,sizeof(prefix),"@%u:%u:%08lx:",id,n,(unsigned long)transport_crc(text,n));
 uart_text(prefix,k);uart_text(text,n);uart_text("\r\n",2);
}
static void transport_error(unsigned id,const char *reason){
 char text[160];unsigned n=(unsigned)snprintf(text,sizeof(text),"{\"ok\":0,\"transport_error\":\"%s\"}",reason);
 transport_send(id,text,n);
}
#endif
