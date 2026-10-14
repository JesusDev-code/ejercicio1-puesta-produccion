import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { Api } from '../core/api';
import { codigo } from '../core/errores';
import { ACCIONES_AUDITORIA, AUDITORIA_ALERTA, AUDITORIA_PRIVILEGIO, RegistroAuditoria } from '../core/modelos';
import { Cargando, FalloServidor } from '../ui/estados';

const POR_PAGINA = 50;

@Component({
  selector: 'app-auditoria',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, DecimalPipe, Cargando, FalloServidor],
  template: `
    <div class="pila">
      <header class="cabecera">
        <div class="textos">
          <span class="ruta">~/auditoria</span>
          <h1 class="titulo">Auditoría</h1>
          <p class="subtitulo">Registro inmutable de las acciones sensibles, incluidos los incidentes borrados.</p>
        </div>
        <form role="search" aria-label="Filtro de auditoría" class="filtro" (ngSubmit)="filtrar()">
          <div class="campo">
            <label for="a-accion" class="etiqueta-filtro">Acción</label>
            <select id="a-accion" class="entrada compacta mono" [formControl]="accion">
              <option value="">todas</option>
              @for (a of acciones; track a) { <option [value]="a">{{ a }}</option> }
            </select>
          </div>
          <button type="submit" class="btn btn-oro">Filtrar</button>
        </form>
      </header>

      <div class="leyenda">
        <span><span aria-hidden="true" class="punto alerta"></span>Alerta de seguridad</span>
        <span><span aria-hidden="true" class="punto privilegio"></span>Privilegios o borrado</span>
        <span><span aria-hidden="true" class="punto normal"></span>Operación normal</span>
      </div>

      <section aria-label="Registro" class="terminal">
        <div class="barra-terminal">
          <span aria-hidden="true" class="luz roja"></span>
          <span aria-hidden="true" class="luz ambar"></span>
          <span aria-hidden="true" class="luz apagada"></span>
          <span class="mono comando">tail -n {{ porPagina }} auditoria.log{{ accion.value ? ' | grep ' + accion.value : '' }}</span>
        </div>

        @if (cargando()) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else {
          <div class="desplazable">
            <div class="registro mono" role="table" aria-label="Entradas de auditoría">
              <div class="linea cabecera-linea" role="row">
                <span role="columnheader">FECHA (UTC)</span><span role="columnheader">USUARIO</span><span role="columnheader">ACCIÓN</span>
                <span role="columnheader">RECURSO</span><span role="columnheader">IP</span><span role="columnheader">DETALLE</span>
              </div>
              @for (r of filas(); track r.id) {
                <div class="linea" role="row" [class]="tipo(r.accion)">
                  <span role="cell" class="fecha">{{ r.fecha | date: 'yyyy-MM-dd HH:mm:ss' : 'UTC' }}</span>
                  <span role="cell" class="usuario">{{ r.usuario_email ?? (r.usuario_id ? '#' + r.usuario_id : '—') }}</span>
                  <span role="cell" class="accion">{{ r.accion }}</span>
                  <span role="cell" class="tenue">{{ r.recurso }}{{ r.recurso_id ? ' #' + r.recurso_id : '' }}</span>
                  <span role="cell" class="tenue">{{ r.ip ?? '—' }}</span>
                  <span role="cell" class="detalle">{{ r.detalle ?? '—' }}</span>
                </div>
              } @empty {
                <div class="linea vacia">sin entradas</div>
              }
              <div class="fin">&gt; fin del bloque<span class="cursor">_</span></div>
            </div>
          </div>
        }
      </section>

      @if (total() > 0) {
        <nav aria-label="Paginación" class="paginacion sin-relleno">
          <span>Mostrando {{ desplazamiento() + 1 }}–{{ desplazamiento() + filas().length }} de {{ total() | number }}</span>
          <div class="botones">
            <button type="button" class="btn btn-suave" [disabled]="desplazamiento() === 0" (click)="pagina(-1)">← Más recientes</button>
            <button type="button" class="btn btn-suave" [disabled]="desplazamiento() + filas().length >= total()" (click)="pagina(1)">Más antiguos →</button>
          </div>
        </nav>
      }
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 28px; }
    .cabecera { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-end; justify-content: space-between; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .filtro { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
    .filtro .campo { gap: 6px; min-width: 240px; }
    .etiqueta-filtro { font-size: 12px !important; color: var(--apagado) !important; }
    .leyenda { display: flex; flex-wrap: wrap; gap: 20px; font-size: 12px; color: var(--apagado); }
    .leyenda > span { display: inline-flex; align-items: center; gap: 8px; }
    .punto.alerta { color: #ff4d5e; } .punto.privilegio { color: #f0c987; } .punto.normal { color: #8fd3b8; }
    .terminal {
      border-radius: 24px; overflow: hidden;
      background: linear-gradient(180deg, rgba(10, 6, 10, 0.75), rgba(10, 6, 10, 0.55));
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.03), 0 40px 90px -40px rgba(0, 0, 0, 0.95);
    }
    .barra-terminal { display: flex; align-items: center; gap: 8px; padding: 14px 20px; background: rgba(255, 255, 255, 0.03); }
    .luz { width: 10px; height: 10px; border-radius: 50%; }
    .luz.roja { background: #e01e3c; box-shadow: 0 0 8px #e01e3c; }
    .luz.ambar { background: #b08a45; }
    .luz.apagada { background: #3a2a30; }
    .comando { margin-left: 10px; font-size: 12px; color: var(--tenue); overflow-wrap: anywhere; }
    .desplazable { overflow-x: auto; }
    .registro { min-width: 940px; padding: 10px 8px 6px; font-size: 12.5px; }
    .linea {
      display: grid; grid-template-columns: 160px 200px 180px 130px 120px minmax(0, 1fr); gap: 16px;
      padding: 9px 14px; border-radius: 10px; line-height: 1.5; transition: background 0.2s;
    }
    .linea:hover { background: rgba(255, 255, 255, 0.04); }
    .cabecera-linea { padding: 8px 14px; font-size: 10px; letter-spacing: 2px; color: var(--tenue); }
    .cabecera-linea:hover { background: none; }
    .fecha { color: var(--tenue); }
    .usuario { color: #dccdd1; overflow-wrap: anywhere; }
    .tenue { color: var(--apagado); overflow-wrap: anywhere; }
    .detalle { color: var(--texto-2); overflow-wrap: anywhere; }
    .accion { color: #8fd3b8; }
    .privilegio .accion { color: #f0c987; }
    .alerta { background: rgba(224, 30, 60, 0.09); }
    .alerta .accion { color: #ff4d5e; text-shadow: 0 0 12px rgba(255, 77, 94, 0.7); }
    .vacia { display: block; color: var(--apagado); }
    .fin { padding: 10px 14px 12px; color: var(--sangre-claro); }
    .relleno { padding: 24px; }
    .sin-relleno { padding: 0; }
    .botones { display: flex; gap: 8px; }
  `,
})
export class Auditoria implements OnInit {
  private readonly api = inject(Api);

  protected readonly acciones = ACCIONES_AUDITORIA;
  protected readonly porPagina = POR_PAGINA;
  protected readonly accion = new FormControl('', { nonNullable: true });

  protected readonly filas = signal<RegistroAuditoria[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);

  ngOnInit(): void {
    void this.cargar();
  }

  protected tipo(accion: string): string {
    if (AUDITORIA_ALERTA.has(accion)) return 'alerta';
    if (AUDITORIA_PRIVILEGIO.has(accion)) return 'privilegio';
    return '';
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      const pagina = await this.api.auditoria({
        accion: this.accion.value,
        limite: POR_PAGINA,
        desplazamiento: this.desplazamiento(),
      });
      this.filas.set(pagina.elementos);
      this.total.set(pagina.total);
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  filtrar(): void {
    this.desplazamiento.set(0);
    void this.cargar();
  }

  pagina(direccion: 1 | -1): void {
    this.desplazamiento.update((d) => Math.max(0, d + direccion * POR_PAGINA));
    void this.cargar();
  }
}
