# Firmware artifacts

Esta Ã¡rea contÃ©m manifests, relatÃ³rios, patches pequenos e artefatos derivados.
Dumps SPI integrais ficam fora do projeto, em armazenamento privado.

`manifests/` identifica entradas e hashes; `patches/` contÃ©m experimentos
reversÃ­veis ou explicitamente rejeitados.

Antes de remover qualquer artefato derivado, consulte [`sources.md`](sources.md).
Ele fixa o arquivo BIOS de origem, hashes, ferramentas, GUID e comandos para
reproduzir e validar localmente o Setup PE32, o IFR e a candidata MADT.
