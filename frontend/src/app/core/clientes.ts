import { Injectable, computed, inject, signal } from '@angular/core';

import { Api } from './api';
import { Empresa, SIN_EMPRESA } from './modelos';
import { Opcion } from '../ui/selector';

/**
 * Caché de los clientes (empresas) para traducir `empresa_id` a nombre y montar los selectores.
 * Solo la usa el admin: la API responde 403 a cualquier otro rol.
 */
@Injectable({ providedIn: 'root' })
export class Clientes {
  private readonly api = inject(Api);
  private cargaEnCurso: Promise<void> | null = null;

  readonly lista = signal<Empresa[]>([]);
  private readonly porId = computed(() => new Map(this.lista().map((e) => [e.id, e])));

  /** Opciones de filtro: todos los clientes, más «Todos». */
  readonly opcionesFiltro = computed<Opcion<number | null>[]>(() => [
    { valor: null, etiqueta: 'Todos los clientes' },
    ...this.lista().map((e) => ({ valor: e.id, etiqueta: e.activa ? e.nombre : `${e.nombre} (baja)` })),
  ]);

  /** Opciones de alta: solo clientes activos, más el personal propio. */
  readonly opcionesAlta = computed<Opcion<number | null>[]>(() => [
    { valor: null, etiqueta: `${SIN_EMPRESA} (personal propio)` },
    ...this.lista()
      .filter((e) => e.activa)
      .map((e) => ({ valor: e.id, etiqueta: e.nombre })),
  ]);

  /** Carga una vez; `forzar` tras crear o editar un cliente. */
  cargar(forzar = false): Promise<void> {
    if (forzar || !this.cargaEnCurso) {
      this.cargaEnCurso = this.api
        .empresas()
        .then((p) => this.lista.set(p.elementos))
        .catch(() => {
          this.cargaEnCurso = null; // se reintenta en la próxima llamada
        });
    }
    return this.cargaEnCurso;
  }

  nombre(id: number | null): string {
    if (id === null) return SIN_EMPRESA;
    return this.porId().get(id)?.nombre ?? `Cliente #${id}`;
  }

  /** Para refrescar la lista sin otra petición cuando ya se tiene la empresa nueva. */
  actualizar(empresa: Empresa): void {
    this.lista.update((lista) => {
      const sin = lista.filter((e) => e.id !== empresa.id);
      return [...sin, empresa].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
    });
  }
}
