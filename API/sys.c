#include "sys.h"


//THUMB指令不支持汇编内联
//采用如下方法实现执行汇编指令WFI
__attribute__((naked)) void WFI_SET(void)
{
    __asm volatile("wfi");
}

//关闭所有中断(但是不包括fault和NMI中断)
__attribute__((naked)) void INTX_DISABLE(void)
{
    __asm volatile("cpsid i");
    __asm volatile("bx lr");
}

//开启所有中断
__attribute__((naked)) void INTX_ENABLE(void)
{
    __asm volatile("cpsie i");
    __asm volatile("bx lr");
}

//设置栈顶地址
//addr:栈顶地址
__attribute__((naked)) void MSR_MSP(u32 addr)
{
    __asm volatile("msr msp, r0");
    __asm volatile("bx lr");
}

