/* Stack paint measures a conservative high-water bound, not DDR capacity.
 * Paint only unused stack below the current SP. Heap accounting tracks every
 * _sbrk extension (including libc), rather than guessing from the linker size.
 */
#include <stddef.h>
#include <errno.h>
extern char _stack_end, _stack, _heap_start, _heap_end;
static uintptr_t heap_break,heap_peak,stack_paint_end;
static unsigned stack_guard_ok=1,heap_failures;
static const uint32_t STACK_PAINT=0x8d31c6a7U;
void *_sbrk(ptrdiff_t increment){
 uintptr_t before=heap_break?heap_break:(uintptr_t)&_heap_start;
 intptr_t after=(intptr_t)before+increment;
 if(after<(intptr_t)&_heap_start||after>(intptr_t)&_heap_end){errno=ENOMEM;heap_failures++;return (void*)-1;}
 heap_break=(uintptr_t)after;if(heap_break>heap_peak)heap_peak=heap_break;
 return (void*)before;
}
static void memory_init(void){
 uintptr_t sp;volatile uint32_t *p;
 __asm__ volatile("mov %0, sp":"=r"(sp));
 stack_paint_end=(sp-256)&~(uintptr_t)3;
 for(p=(volatile uint32_t*)&_stack_end;(uintptr_t)p<stack_paint_end;p++)*p=STACK_PAINT;
}
static void memory_report(void){
 volatile uint32_t *p=(volatile uint32_t*)&_stack_end;unsigned painted=0,cpsr;
 while((uintptr_t)p<stack_paint_end&&*p==STACK_PAINT){painted+=4;p++;}
 stack_guard_ok=painted>=256;
 __asm__ volatile("mrs %0, cpsr":"=r"(cpsr));
 reply("{\"ok\":1,\"type\":\"MEMORY\",\"method\":\"stack_paint_conservative_bound_and_sbrk_peak\",\"stack_reserved\":%u,\"stack_peak_bound\":%u,\"stack_guard_ok\":%u,\"heap_reserved\":%u,\"heap_committed_peak\":%u,\"heap_committed_now\":%u,\"heap_failures\":%u,\"cpu_mode\":%u}",
 (unsigned)(&_stack-&_stack_end),(unsigned)(&_stack-&_stack_end)-painted,stack_guard_ok,
 (unsigned)(&_heap_end-&_heap_start),heap_peak?(unsigned)(heap_peak-(uintptr_t)&_heap_start):0,
 heap_break?(unsigned)(heap_break-(uintptr_t)&_heap_start):0,heap_failures,cpsr&31);
}
