#include <assert.h>
#include <stdio.h>
#include "dedup_cache.h"
int main(void){
 unsigned i;
 seen_reset();assert(!seen_contains(0,12,123,0));seen_insert(0,12,123,0);
 /* Regression: other traffic during an ACK outage used to evict this packet
  * after 64 accepts, although it could still be retried for 60 seconds. */
 for(i=0;i<12000;i++)seen_insert(i%17,1+i%16,1000+i,i%1024);
 assert(seen_contains(0,12,123,0));
 assert(!seen_contains(0,11,123,0));assert(!seen_contains(1,12,123,0));assert(!seen_contains(0,12,123,1));
 for(i=0;i<12000;i++)assert(seen_contains(i%17,1+i%16,1000+i,i%1024));
 /* Wrap and hash collisions must not create a false hit or lose recent keys. */
 for(i=0;i<50000;i++)seen_insert(i%17,1+i%16,100000+i,i%1024);
 for(i=50000-SEEN_CAPACITY;i<50000;i++)assert(seen_contains(i%17,1+i%16,100000+i,i%1024));
 assert(!seen_contains(0,12,123,0));
 seen_reset();assert(!seen_contains(0,12,123,0));
 printf("DEDUP_RETENTION_PASS capacity=%u bytes=%u live_upper_bound=12000\n",SEEN_CAPACITY,(unsigned)(sizeof(seen)+sizeof(seen_buckets)));
 return 0;
}
