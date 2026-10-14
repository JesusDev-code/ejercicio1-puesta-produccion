import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo } from '../core/errores';
import {
  CATEGORIAS,
  Categoria,
  ESTADOS,
  Estado,
  Incidente,
  SEVERIDADES,
  Severidad,
  codigoInc,
  entradas,
} from '../core/modelos';
import { Sesion } from '../core/sesion';
import { Cargando, FalloServidor } from '../ui/estados';
import { PildoraEstado, PildoraSeveridad } from '../ui/pildoras';

const POR_PAGINA = 10;

interface Contador {
  etiqueta: string;
  clase: string;
  valor: number | null;
}

@Component({
  selector: 'app-incidentes',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, DecimalPipe, PildoraEstado, PildoraSeveridad, Cargando, FalloServidor],
  template: `
    <div class="pila">
      <header class="cabecera">
        <div class="textos">
          <span class="ruta">~/incidentes</span>
          <h1 class="titulo">{{ textos().titulo }}</h1>
          <p class="subtitulo">{{ textos().subtitulo }}</p>
        </div>
        <a routerLink="/incidentes/nuevo" class="btn btn-sangre"><span aria-hidden="true" class="mas">+</span> Nuevo incidente</a>
      </header>

      <section aria-label="Resumen por estado" class="resumen">
        @for (c of contadores(); track c.etiqueta) {
          <div class="contador-tarjeta" [class]="c.clase">
            <span aria-hidden="true" class="halo-tarjeta"></span>
            <span class="cabecera-mono etiqueta-contador">{{ c.etiqueta }}</span>
            <span class="valor">{{ c.valor === null ? '—' : (c.valor | number: '2.0-0') }}</span>
          </div>
        }
      </section>

      <section aria-label="Incidentes" class="cristal panel">
        <form role="search" aria-label="Filtros" class="filtros" [formGroup]="filtros" (ngSubmit)="aplicar()">
          <div class="campo">
            <label for="f-estado">Estado</label>
            <select id="f-estado" class="entrada compacta" formControlName="estado">
              <option value="">Todos</option>
              @for (e of estados; track e[0]) { <option [value]="e[0]">{{ e[1].nombre }}</option> }
            </select>
          </div>
          <div class="campo">
            <label for="f-sev">Severidad</label>
            <select id="f-sev" class="entrada compacta" formControlName="severidad">
              <option value="">Todas</option>
              @for (s of severidades; track s[0]) { <option [value]="s[0]">{{ s[1].nombre }}</option> }
            </select>
          </div>
          <div class="campo ancho">
            <label for="f-cat">Categoría</label>
            <select id="f-cat" class="entrada compacta" formControlName="categoria">
              <option value="">Todas</option>
              @for (c of categorias; track c[0]) { <option [value]="c[0]">{{ c[1] }}</option> }
            </select>
          </div>
          <button type="submit" class="btn btn-oro">Aplicar</button>
          <button type="button" class="btn btn-texto" (click)="limpiar()">Limpiar</button>
        </form>

        @if (cargando()) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else if (filas().length === 0) {
          <div class="vacio">
            <pre aria-hidden="true" class="terminal">$ ls ~/incidentes
total 0<span class="cursor">_</span></pre>
            <h2 class="titulo-2 grande">{{ hayFiltros() ? 'Nada con estos filtros' : 'Todavía no hay incidentes' }}</h2>
            <div class="acciones">
              @if (hayFiltros()) { <button type="button" class="btn btn-oro" (click)="limpiar()">Limpiar filtros</button> }
              <a routerLink="/incidentes/nuevo" class="btn btn-sangre">+ Nuevo incidente</a>
            </div>
          </div>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">ID</th>
                  <th scope="col">INCIDENTE</th>
                  <th scope="col">SEVERIDAD</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ANALISTA</th>
                  <th scope="col">ACTUALIZADO</th>
                </tr>
              </thead>
              <tbody>
                @for (f of filas(); track f.id) {
                  <tr class="fila">
                    <td class="mono id">{{ codigoInc(f.id) }}</td>
                    <td>
                      <a [routerLink]="['/incidentes', f.id]" class="enlace-fila">
                        <span class="titulo-fila">{{ f.titulo }}</span>
                        <span class="categoria">{{ categoria(f.categoria) }}</span>
                      </a>
                    </td>
                    <td><app-severidad [valor]="f.severidad" /></td>
                    <td><app-estado [valor]="f.estado" /></td>
                    <td class="analista">{{ f.analista_email ?? 'Sin asignar' }}</td>
                    <td class="mono fecha">{{ f.actualizado_en | date: 'dd/MM HH:mm' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        @if (total() > 0) {
          <nav aria-label="Paginación" class="paginacion">
            <span>Mostrando {{ desde() }}–{{ hasta() }} de {{ total() }}</span>
            <div class="botones">
              <button type="button" class="btn btn-suave" [disabled]="desplazamiento() === 0" (click)="pagina(-1)">← Anterior</button>
              <button type="button" class="btn btn-suave" [disabled]="hasta() >= total()" (click)="pagina(1)">Siguiente →</button>
            </div>
          </nav>
        }
      </section>
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 32px; }
    .cabecera { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-end; justify-content: space-between; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .mas { font-size: 18px; }
    .resumen { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
    .contador-tarjeta {
      position: relative; overflow: hidden; min-width: 0; padding: 22px 22px 20px; border-radius: 20px;
      display: flex; flex-direction: column; gap: 10px;
      background: linear-gradient(160deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.02));
      backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
      --color: #f1e6e0; --halo: rgba(241, 230, 224, 0.22);
    }
    .contador-tarjeta.analisis { --color: #f0c987; --halo: rgba(212, 175, 110, 0.35); }
    .contador-tarjeta.resuelto { --color: #8fd3b8; --halo: rgba(143, 211, 184, 0.28); }
    .contador-tarjeta.critica { --color: #ff4d5e; --halo: rgba(224, 30, 60, 0.5); }
    .halo-tarjeta { position: absolute; right: -30px; top: -30px; width: 110px; height: 110px; border-radius: 50%; background: var(--halo); filter: blur(24px); }
    .etiqueta-contador { position: relative; letter-spacing: 2px; color: var(--apagado); }
    .valor { position: relative; font-family: var(--serif); font-weight: 600; font-size: 52px; line-height: 1; color: var(--color); text-shadow: 0 0 24px var(--halo); }
    .panel { border-radius: 24px; display: flex; flex-direction: column; }
    .filtros .ancho { flex-basis: 200px; }
    .tabla { min-width: 900px; }
    .id { font-size: 12px; color: var(--apagado); white-space: nowrap; }
    .enlace-fila { display: flex; flex-direction: column; gap: 4px; color: var(--texto); text-decoration: none; }
    .enlace-fila:hover .titulo-fila { color: var(--oro-claro); }
    .titulo-fila { font-weight: 600; line-height: 1.4; transition: color 0.2s; }
    .categoria { font-size: 12px; color: var(--apagado); }
    .analista { color: var(--texto-2); font-size: 13px; white-space: nowrap; }
    .fecha { font-size: 12px; color: var(--apagado); white-space: nowrap; }
    .botones { display: flex; gap: 8px; }
    .relleno { padding: 0 24px 24px; }
    .vacio { padding: 12px 30px 30px; display: flex; flex-direction: column; gap: 14px; }
    .terminal { margin: 0; font-family: var(--mono); font-size: 13px; line-height: 1.6; color: var(--sangre-claro); text-shadow: 0 0 12px rgba(255, 77, 94, 0.5); }
    .grande { font-size: 34px; }
    .acciones { display: flex; flex-wrap: wrap; gap: 10px; }
  `,
})
export class Incidentes implements OnInit {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);

  protected readonly estados = entradas(ESTADOS);
  protected readonly severidades = entradas(SEVERIDADES);
  protected readonly categorias = entradas(CATEGORIAS);

  protected readonly filtros = inject(FormBuilder).nonNullable.group({
    estado: '' as Estado | '',
    severidad: '' as Severidad | '',
    categoria: '' as Categoria | '',
  });

  protected readonly filas = signal<Incidente[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly hayFiltros = signal(false);
  protected readonly contadores = signal<Contador[]>([
    { etiqueta: 'ABIERTOS', clase: 'abierto', valor: null },
    { etiqueta: 'EN ANÁLISIS', clase: 'analisis', valor: null },
    { etiqueta: 'RESUELTOS', clase: 'resuelto', valor: null },
    { etiqueta: 'SEVERIDAD CRÍTICA', clase: 'critica', valor: null },
  ]);

  protected readonly desde = computed(() => (this.total() ? this.desplazamiento() + 1 : 0));
  protected readonly hasta = computed(() => this.desplazamiento() + this.filas().length);

  protected readonly textos = computed(() => {
    switch (this.sesion.usuario()?.rol) {
      case 'admin':
        return { titulo: 'Todos los incidentes', subtitulo: 'Vista completa de la organización.' };
      case 'analista':
        return { titulo: 'Mis incidentes', subtitulo: 'Los que tienes asignados y los que has reportado.' };
      default:
        return { titulo: 'Mis incidentes', subtitulo: 'Los incidentes que has reportado.' };
    }
  });

  ngOnInit(): void {
    void this.cargar();
    void this.cargarContadores();
  }

  protected readonly codigoInc = codigoInc;

  protected categoria(c: Categoria): string {
    return CATEGORIAS[c];
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      const pagina = await this.api.incidentes({
        ...this.filtros.getRawValue(),
        limite: POR_PAGINA,
        desplazamiento: this.desplazamiento(),
      });
      this.filas.set(pagina.elementos);
      this.total.set(pagina.total);
    } catch (e) {
      this.fallo.set(codigo(e));
      this.filas.set([]);
      this.total.set(0);
    } finally {
      this.cargando.set(false);
    }
  }

  /** Contadores con `limite=1`: solo interesa `total`, no las filas. */
  private async cargarContadores(): Promise<void> {
    const consultas = [
      this.api.incidentes({ estado: 'abierto', limite: 1 }),
      this.api.incidentes({ estado: 'en_analisis', limite: 1 }),
      this.api.incidentes({ estado: 'resuelto', limite: 1 }),
      this.api.incidentes({ severidad: 'critica', limite: 1 }),
    ];
    const resultados = await Promise.allSettled(consultas);
    this.contadores.update((lista) =>
      lista.map((c, i) => {
        const r = resultados[i];
        return { ...c, valor: r.status === 'fulfilled' ? r.value.total : null };
      }),
    );
  }

  aplicar(): void {
    const v = this.filtros.getRawValue();
    this.hayFiltros.set(Boolean(v.estado || v.severidad || v.categoria));
    this.desplazamiento.set(0);
    void this.cargar();
  }

  limpiar(): void {
    this.filtros.reset();
    this.aplicar();
  }

  pagina(direccion: 1 | -1): void {
    this.desplazamiento.update((d) => Math.max(0, d + direccion * POR_PAGINA));
    void this.cargar();
  }
}
