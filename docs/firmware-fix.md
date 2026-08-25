# Firmware fix

A candidata MADT em `firmware/patches/candidates/` altera somente os UIDs das
entradas Local APIC NMI de `1..16` para `0..15`, preservando o restante da
imagem e recalculando o checksum.

Ela foi entregue ao Windows por OpenCore, mas nÃ£o demonstrou ser suficiente
para iniciar o Hyper-V. Portanto Ã© uma candidata de investigaÃ§Ã£o, nÃ£o uma BIOS
pronta para flash. O rebuild rejeitado permanece marcado em
`archive/experiments/rejected/`.

Imagens SPI integrais de recuperaÃ§Ã£o nÃ£o fazem parte deste repositÃ³rio pÃºblico.
