import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { Clientes } from '../core/clientes';
import { codigo } from '../core/errores';
import { Sensor } from '../core/modelos';
import { Cargando, FalloServidor } from '../ui/estados';

/** Sin eventos en este tiempo, el sensor se marca como silencioso: puede estar caído. */
const SILENCIO_MINUTOS = 15;

const NOMBRES_SERVICIO: Record<string, string> = {
  senuelo: 'Señuelo',
  'generador-demo': 'Generador de demo',
};

@Component({
  selector: 'app-sensores',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, DatePipe, DecimalPipe, Cargando, FalloServidor],
  styleUrl: './usuarios.css',
  template: `
    <div class="pila">
      <header class="cabecera">
        <div class="textos">
          <span class="ruta">~/sensores</span>
          <h1 class="titulo">Sensores</h1>
          <p class="subtitulo">
            Cada sensor desplegado y de qué cliente es, según los eventos que envía. Si uno lleva más de {{ silencio }} minutos sin enviar nada, se marca como silencioso: revisa que siga en marcha.
          </p>
        </div>
        <button type="button" class="btn btn-oro" [disabled]="cargando()" (click)="cargar()">Actualizar</button>
      </header>

      <section aria-label="Sensores" class="cristal panel">
        @if (cargando() && filas().length === 0) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else if (filas().length === 0) {
          <p class="vacio">Todavía no ha llegado ningún evento: no hay sensores que mostrar.</p>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">SENSOR</th>
                  <th scope="col">CLIENTE</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ÚLTIMO EVENTO</th>
                  <th scope="col">24 H</th>
                  <th scope="col">TOTAL</th>
                  <th scope="col"><span class="solo-lector">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                @for (s of filas(); track s.servicio + '-' + s.empresa_id) {
                  <tr class="fila">
                    <td>
                      <div class="datos">
                        <span class="email">{{ nombreServicio(s.servicio) }}</span>
                        <span class="mono id">{{ s.servicio }}</span>
                      </div>
                    </td>
                    <td>{{ clientes.nombre(s.empresa_id) }}</td>
                    <td>
                      <span class="estado" [class.activo]="activo(s)"><span aria-hidden="true" class="punto"></span>{{ activo(s) ? 'Enviando' : 'Silencioso' }}</span>
                    </td>
                    <td class="mono alta-fecha">{{ s.ultimo | date: 'dd/MM HH:mm:ss' }}</td>
                    <td class="mono">{{ s.ultimas_24h | number }}</td>
                    <td class="mono">{{ s.total | number }}</td>
                    <td class="acciones">
                      @if (s.empresa_id !== null) {
                        <a class="btn compacto btn-suave" [routerLink]="['/eventos']" [queryParams]="{ empresa: s.empresa_id }">Ver eventos</a>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>
  `,
})
export class Sensores implements OnInit {
  private readonly api = inject(Api);
  protected readonly clientes = inject(Clientes);

  protected readonly silencio = SILENCIO_MINUTOS;
  protected readonly filas = signal<Sensor[]>([]);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  /** Momento de la última carga: el estado se calcula contra él, no contra el reloj en vivo. */
  private consultado = Date.now();

  ngOnInit(): void {
    void this.clientes.cargar();
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      this.filas.set(await this.api.sensores());
      this.consultado = Date.now();
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  protected activo(s: Sensor): boolean {
    return this.consultado - new Date(s.ultimo).getTime() < SILENCIO_MINUTOS * 60_000;
  }

  protected nombreServicio(servicio: string): string {
    return NOMBRES_SERVICIO[servicio] ?? servicio;
  }
}
