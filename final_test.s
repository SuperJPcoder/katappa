.section .rodata
.L_STR_1: .string "Starting loop from 0 to 9..."
.L_STR_2: .string "Halfway there!"
.L_STR_3: .string "Loop finished!"
.L_STR_4: .string "The final value of .i is correct."
.L_STR_5: .string "Something went wrong!"
.LC_NUM_FMT: .string "%lld\n"
.section .text
.globl main

main:
    pushq   %rbp
    movq    %rsp, %rbp
    subq    $32, %rsp

    # Katappa: .limit = ...
    movq    $10, -16(%rbp)

    # Katappa: .i = ...
    movq    $0, -8(%rbp)

    # Katappa: .zero = ...
    movq    $0, -24(%rbp)

    # Katappa: print "Starting loop from 0 to 9...";
    leaq    .L_STR_1(%rip), %rcx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp

.L_LOOP_START_6:

    # Katappa: when .i >= .limit {...}
    movq    -8(%rbp), %rax
    cmpq    -16(%rbp), %rax
    jl .L_ELSE_8
    jmp .L_LOOP_END_7
    jmp .L_END_WHEN_9
.L_ELSE_8:
.L_END_WHEN_9:

    # Katappa: print .i;
    leaq    .LC_NUM_FMT(%rip), %rcx
    movq    -8(%rbp), %rdx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp

    # Katappa: when .i == 5 {...}
    movq    -8(%rbp), %rax
    cmpq    $5, %rax
    jne .L_ELSE_10

    # Katappa: print "Halfway there!";
    leaq    .L_STR_2(%rip), %rcx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp
    jmp .L_END_WHEN_11
.L_ELSE_10:
.L_END_WHEN_11:

    # Katappa: .i = ...
    movq    -8(%rbp), %rax
    addq   $1, %rax
    movq    %rax, -8(%rbp)
    jmp .L_LOOP_START_6
.L_LOOP_END_7:

    # Katappa: print "Loop finished!";
    leaq    .L_STR_3(%rip), %rcx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp

    # Katappa: when .i == .limit {...}
    movq    -8(%rbp), %rax
    cmpq    -16(%rbp), %rax
    jne .L_ELSE_12

    # Katappa: print "The final value of .i is correct.";
    leaq    .L_STR_4(%rip), %rcx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp
    jmp .L_END_WHEN_13
.L_ELSE_12:

    # Katappa: print "Something went wrong!";
    leaq    .L_STR_5(%rip), %rcx
    subq    $32, %rsp
    movq    $0, %rax
    call    printf
    addq    $32, %rsp
.L_END_WHEN_13:

    movq    $0, %rax
    leave
    ret
