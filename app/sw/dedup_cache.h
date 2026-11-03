#ifndef SWARM_DEDUP_CACHE_H
#define SWARM_DEDUP_CACHE_H
#include <stdint.h>
#include <string.h>
/* One accepted DATA frame per 5 ms TDMA slot, across the entire system:
 * at most 200 new entries/s, and retry lifetime <=60 model seconds.
 * 16384 exact entries therefore outlive all 12000 potentially live entries.
 * Hash chaining is only an index: collisions always compare the full key.
 * This bound must be revisited if TDMA or the retry lifetime changes. */
#define SEEN_CAPACITY 16384U
#define SEEN_BUCKETS 8192U
#define SEEN_NONE 65535U
typedef struct {
 uint32_t seq;
 uint16_t frag,next;
 uint8_t source,node,valid;
} Seen;
static Seen seen[SEEN_CAPACITY];
static uint16_t seen_buckets[SEEN_BUCKETS];
static unsigned seen_head;
static unsigned seen_hash(unsigned node,unsigned source,uint32_t seq,unsigned frag){
 uint32_t h=seq^((uint32_t)frag*0x9e3779b9U)^((uint32_t)node<<24)^((uint32_t)source<<16);
 h^=h>>16;h*=0x7feb352dU;h^=h>>15;
 return h&(SEEN_BUCKETS-1U);
}
static void seen_reset(void){
 memset(seen,0,sizeof(seen));memset(seen_buckets,255,sizeof(seen_buckets));seen_head=0;
}
static int seen_contains(unsigned node,unsigned source,uint32_t seq,unsigned frag){
 unsigned i=seen_buckets[seen_hash(node,source,seq,frag)];
 while(i!=SEEN_NONE){Seen*s=&seen[i];if(s->node==node&&s->source==source&&s->seq==seq&&s->frag==frag)return 1;i=s->next;}
 return 0;
}
static void seen_insert(unsigned node,unsigned source,uint32_t seq,unsigned frag){
 unsigned slot=seen_head++&(SEEN_CAPACITY-1U),bucket;
 Seen*s=&seen[slot];
 if(s->valid){
  uint16_t *link=&seen_buckets[seen_hash(s->node,s->source,s->seq,s->frag)];
  while(*link!=slot&&*link!=SEEN_NONE)link=&seen[*link].next;
  if(*link==slot)*link=s->next;
 }
 bucket=seen_hash(node,source,seq,frag);
 s->seq=seq;s->frag=frag;s->source=source;s->node=node;s->valid=1;
 s->next=seen_buckets[bucket];seen_buckets[bucket]=(uint16_t)slot;
}
#endif
