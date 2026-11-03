// CCITT-FALSE: MSB first, poly 0x1021, initial state 0xFFFF.
function automatic [15:0] crc16_step;
    input [15:0] state;
    input data_bit;
    begin
        crc16_step = {state[14:0], 1'b0};
        if (state[15] ^ data_bit)
            crc16_step = crc16_step ^ 16'h1021;
    end
endfunction
