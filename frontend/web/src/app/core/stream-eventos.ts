import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { EventoSeguridad } from './modelos';
import { Sesion } from './sesion';

/**
 * Suscripción al flujo de eventos en vivo (SSE de /api/eventos/stream).
 *
 * No se usa EventSource: no deja poner la cabecera Authorization, y aquí el token de acceso
 * vive en memoria (no en una cookie). En su lugar, fetch con el cuerpo en streaming, que sí
 * admite cabeceras. Ante un corte reconecta con una espera creciente; ante un 401 refresca el
 * token una vez. El servidor cierra cada ~10 min (evento `fin`) y aquí se reconecta solo.
 */
@Injectable({ providedIn: 'root' })
export class StreamEventos {
  private readonly sesion = inject(Sesion);

  /**
   * Abre el flujo y llama a `alEvento` por cada evento nuevo. Devuelve una función para cerrarlo.
   * `alEstado` informa de si está conectado, para pintar el indicador.
   */
  suscribir(
    alEvento: (e: EventoSeguridad) => void,
    alEstado?: (conectado: boolean) => void,
  ): () => void {
    const control = new AbortController();
    let espera = 1000;
    let reintentado401 = false;

    const conectar = async (): Promise<void> => {
      while (!control.signal.aborted) {
        try {
          const token = this.sesion.tokenAcceso();
          const respuesta = await fetch('/api/eventos/stream', {
            headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
            signal: control.signal,
          });

          if (respuesta.status === 401 && !reintentado401) {
            // Token caducado: un refresco y se reintenta de inmediato
            reintentado401 = true;
            await this.refrescar();
            continue;
          }
          if (!respuesta.ok || !respuesta.body) {
            throw new Error(`stream ${respuesta.status}`);
          }

          reintentado401 = false;
          espera = 1000;
          alEstado?.(true);
          await this.leer(respuesta.body, alEvento, control.signal);
        } catch (e) {
          if (control.signal.aborted) return;
          void e;
        }
        // Se llega aquí cuando el servidor cierra o hay un corte: reconectar con backoff
        alEstado?.(false);
        await this.dormir(espera, control.signal);
        espera = Math.min(espera * 2, 15000);
      }
    };

    void conectar();
    return () => {
      control.abort();
      alEstado?.(false);
    };
  }

  private async leer(
    cuerpo: ReadableStream<Uint8Array>,
    alEvento: (e: EventoSeguridad) => void,
    signal: AbortSignal,
  ): Promise<void> {
    const lector = cuerpo.getReader();
    const decodificador = new TextDecoder();
    let buffer = '';
    try {
      while (!signal.aborted) {
        const { done, value } = await lector.read();
        if (done) return;
        buffer += decodificador.decode(value, { stream: true });
        // Cada mensaje SSE termina en una línea en blanco
        let corte: number;
        while ((corte = buffer.indexOf('\n\n')) !== -1) {
          const bloque = buffer.slice(0, corte);
          buffer = buffer.slice(corte + 2);
          this.procesar(bloque, alEvento);
        }
      }
    } finally {
      lector.cancel().catch(() => undefined);
    }
  }

  private procesar(bloque: string, alEvento: (e: EventoSeguridad) => void): void {
    // Se ignoran los comentarios (`: latido`) y el evento de cierre (`event: fin`)
    let datos = '';
    for (const linea of bloque.split('\n')) {
      if (linea.startsWith('data:')) datos += linea.slice(5).trim();
      if (linea.startsWith('event:') && linea.slice(6).trim() === 'fin') return;
    }
    if (!datos) return;
    try {
      alEvento(JSON.parse(datos) as EventoSeguridad);
    } catch {
      // Un bloque a medias o malformado se descarta sin tirar el flujo
    }
  }

  private async refrescar(): Promise<void> {
    try {
      // Reusa el refresco de la sesión (single-flight): deja el token nuevo en memoria
      await firstValueFrom(this.sesion.refrescar());
    } catch {
      // Si el refresco falla, el próximo ciclo volverá a dar 401 y acabará parando
    }
  }

  private dormir(ms: number, signal: AbortSignal): Promise<void> {
    return new Promise((resolver) => {
      const t = setTimeout(resolver, ms);
      signal.addEventListener('abort', () => {
        clearTimeout(t);
        resolver();
      });
    });
  }
}
