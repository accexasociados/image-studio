# BiRefNet (código copiado)

Arquitectura del modelo de recorte, copiada **sin modificaciones** para no usar `trust_remote_code` (decisión del 2026-10-27, opción C del plan).

| Dato | Valor |
|---|---|
| Origen | https://huggingface.co/ZhengPeng7/BiRefNet (código: https://github.com/ZhengPeng7/BiRefNet) |
| Revisión | `e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4` |
| Licencia | MIT (ver abajo) |
| `birefnet.py` SHA-256 | `208771ae626f653d64128fbf2d6ac9f8e645c5cc5e286258a73ec3322bbfe5ef` |
| `BiRefNet_config.py` SHA-256 | `e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52` |

`tests/test_vendor_birefnet.py` verifica estas firmas: si alguien edita los archivos, el test falla.

## Revisión de seguridad (2026-10-27, claude)

- Sin acceso a red, sin `subprocess`, sin lectura de variables de entorno.
- Los `eval(...)` solo construyen nombres de capas desde textos fijos de la clase `Config` interna; no reciben datos externos.
- La única lectura de archivos (`load_weights` → `torch.load`) ocurre solo si `bb_pretrained=True`. `app/pipeline/segment.py` siempre construye el modelo con `bb_pretrained=False` y carga los pesos desde `model.safetensors` (formato sin pickle).

## Actualizar

1. Descargar la nueva revisión con `scripts/download_models.py` (fijarla en el script).
2. Revisar el diff de `birefnet.py` y `BiRefNet_config.py` con el mismo criterio.
3. Copiar los archivos, actualizar esta tabla y las firmas del test.

## Licencia

MIT License

Copyright (c) 2024 ZhengPeng7

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
