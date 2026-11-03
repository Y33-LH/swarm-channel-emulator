/* Lossless telemetry only: never changes model scheduling or measurements.
 * 32x21 cumulative counters are ULEB128 then base64; IQ is packed LE32 pairs.
 * Buffers are static to preserve the measured ARM stack budget. */
static unsigned char wire_bytes[8192];
static unsigned wire_used;
static void wire_uint(uint64_t v){do{unsigned b=v&127;v>>=7;wire_bytes[wire_used++]=b|(v?128:0);}while(v);}
static unsigned wire_base64(char *dest,size_t capacity){static const char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";unsigned i,n=0;
 if(capacity<4*((wire_used+2)/3)+1){telemetry_overflow=1;if(capacity)dest[0]=0;return 0;}
 for(i=0;i<wire_used;i+=3){unsigned v=(unsigned)wire_bytes[i]<<16;if(i+1<wire_used)v|=(unsigned)wire_bytes[i+1]<<8;if(i+2<wire_used)v|=wire_bytes[i+2];
 dest[n++]=alphabet[(v>>18)&63];dest[n++]=alphabet[(v>>12)&63];dest[n++]=i+1<wire_used?alphabet[(v>>6)&63]:'=';dest[n++]=i+2<wire_used?alphabet[v&63]:'=';}
 dest[n]=0;return n;
}
static void wire_stats(const Stats*s){
 wire_uint(s->attempts);wire_uint(s->captured);wire_uint(s->crc_good);wire_uint(s->acked);wire_uint(s->retries);wire_uint(s->failed);wire_uint(s->duplicates);wire_uint(s->bits);wire_uint(s->errors);wire_uint(s->clipped);wire_uint(s->cycles);wire_uint(s->evm_count);wire_uint(s->evm_count?(unsigned)(s->evm_sum/s->evm_count*1000000):0);wire_uint(s->pre_bits);wire_uint(s->pre_errors);wire_uint(s->fec_frames);wire_uint(s->ack_lost);wire_uint(s->accepted_bytes);wire_uint(s->queue_rejected);wire_uint(s->data_attempts);wire_uint(s->ack_attempts);
}
