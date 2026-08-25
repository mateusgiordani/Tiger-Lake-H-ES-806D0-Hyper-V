/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20260408 (32-bit version)
 * Copyright (c) 2000 - 2026 Intel Corporation
 * 
 * Disassembly of dmar.dat
 *
 * ACPI Data Table [DMAR]
 *
 * Format: [HexOffset DecimalOffset ByteLength]  FieldName : FieldValue (in hex)
 */

[000h 0000 004h]                   Signature : "DMAR"    [DMA Remapping Table]
[004h 0004 004h]                Table Length : 00000050
[008h 0008 001h]                    Revision : 02
[009h 0009 001h]                    Checksum : 3D
[00Ah 0010 006h]                      Oem ID : "INTEL "
[010h 0016 008h]                Oem Table ID : "EDK2    "
[018h 0024 004h]                Oem Revision : 00000002
[01Ch 0028 004h]             Asl Compiler ID : "    "
[020h 0032 004h]       Asl Compiler Revision : 01000013

[024h 0036 001h]          Host Address Width : 26
[025h 0037 001h]                       Flags : 05
[026h 0038 00Ah]                    Reserved : 00 00 00 00 00 00 00 00 00 00

[030h 0048 002h]               Subtable Type : 0000 [Hardware Unit Definition]
[032h 0050 002h]                      Length : 0020

[034h 0052 001h]                       Flags : 01
[035h 0053 001h]        Size (decoded below) : 00
                          Size (pages, log2) : 0
[036h 0054 002h]          PCI Segment Number : 0000
[038h 0056 008h]       Register Base Address : 00000000FED91000

[040h 0064 001h]           Device Scope Type : 03 [IOAPIC Device]
[041h 0065 001h]                Entry Length : 08
[042h 0066 001h]                       Flags : 00
[043h 0067 001h]                    Reserved : 00
[044h 0068 001h]              Enumeration ID : 02
[045h 0069 001h]              PCI Bus Number : 00

[046h 0070 002h]                    PCI Path : 1E,07


[048h 0072 001h]           Device Scope Type : 04 [Message-capable HPET Device]
[049h 0073 001h]                Entry Length : 08
[04Ah 0074 001h]                       Flags : 00
[04Bh 0075 001h]                    Reserved : 00
[04Ch 0076 001h]              Enumeration ID : 00
[04Dh 0077 001h]              PCI Bus Number : 00

[04Eh 0078 002h]                    PCI Path : 1E,06


Raw Table Data: Length 80 (0x50)

    0000: 44 4D 41 52 50 00 00 00 02 3D 49 4E 54 45 4C 20  // DMARP....=INTEL 
    0010: 45 44 4B 32 20 20 20 20 02 00 00 00 20 20 20 20  // EDK2    ....    
    0020: 13 00 00 01 26 05 00 00 00 00 00 00 00 00 00 00  // ....&...........
    0030: 00 00 20 00 01 00 00 00 00 10 D9 FE 00 00 00 00  // .. .............
    0040: 03 08 00 00 02 00 1E 07 04 08 00 00 00 00 1E 06  // ................
