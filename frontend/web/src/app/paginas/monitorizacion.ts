import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { EventoSeguridad, ResumenEventos, SEVERIDADES, Severidad, TIPOS_EVENTO } from '../core/modelos';
import { StreamEventos } from '../core/stream-eventos';
import { Barra, GraficoBarras } from '../ui/grafico-barras';
import { GraficoLineas } from '../ui/grafico-lineas';
import { Cargando, FalloServidor } from '../ui/estados';
import { Opcion, Selector } from '../ui/selector';

const MAX_FEED = 40;

@Component({
  selector: 'app-monitorizacion',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, RouterLink, GraficoLineas, GraficoBarras, Cargando, FalloServidor, Selector],
  templateUrl: './monitorizacion.html',
  styleUrl: './monitorizacion.css',
})
export class Monitorizacion implements OnInit {
  private readonly api = inject(Api);
  private readonly stream = inject(StreamEventos);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly TIPOS = TIPOS_EVENTO;
  protected readonly feedMax = MAX_FEED;
  protected readonly SEV = SEVERIDADES;

  protected readonly rangos: Opcion<number>[] = [
    { valor: 1, etiqueta: 'Última hora' },
    { valor: 24, etiqueta: 'Últimas 24 h' },
    { valor: 168, etiqueta: 'Últimos 7 días' },
  ];
  protected readonly horas = signal(24);

  protected readonly resumen = signal<ResumenEventos | null>(null);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);

  protected readonly feed = signal<EventoSeguridad[]>([]);
  protected readonly enVivo = signal(false);
  protected readonly creando = signal<number | null>(null);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);

  // La serie temporal usa minutos en la última hora y horas en los rangos largos
  protected readonly serie = computed(() => {
    const r = this.resumen();
    if (!r) return { datos: [], unidad: 'minuto' as const, etiqueta: '' };
    return this.horas() <= 1
      ? { datos: r.por_minuto, unidad: 'minuto' as const, etiqueta: 'Eventos por minuto (última hora)' }
      : { datos: r.por_hora.slice(-this.horas()), unidad: 'hora' as const, etiqueta: 'Eventos por hora' };
  });

  protected readonly etiquetaRango = computed(
    () => this.rangos.find((r) => r.valor === this.horas())?.etiqueta ?? '',
  );

  protected readonly barrasTipo = computed<Barra[]>(
    () => this.resumen()?.por_tipo.map((r) => ({ etiqueta: TIPOS_EVENTO[r.clave as keyof typeof TIPOS_EVENTO] ?? r.clave, valor: r.total })) ?? [],
  );
  protected readonly barrasSeveridad = computed<Barra[]>(
    () =>
      this.resumen()?.por_severidad.map((r) => ({
        etiqueta: SEVERIDADES[r.clave as Severidad]?.nombre ?? r.clave,
        valor: r.total,
        clase: `c-${r.clave}`,
      })) ?? [],
  );
  protected readonly barrasIp = computed<Barra[]>(
    () => this.resumen()?.top_ips.map((r) => ({ etiqueta: r.clave, valor: r.total })) ?? [],
  );

  ngOnInit(): void {
    void this.cargar();
    const cerrar = this.stream.suscribir(
      (e) => this.feed.update((lista) => [e, ...lista].slice(0, MAX_FEED)),
      (conectado) => this.enVivo.set(conectado),
    );
    this.destroyRef.onDestroy(cerrar);
  }

  cambiarRango(horas: number): void {
    this.horas.set(horas);
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      this.resumen.set(await this.api.resumenEventos(this.horas()));
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  async crearIncidencia(e: EventoSeguridad): Promise<void> {
    if (e.incidente_id) {
      await this.router.navigate(['/incidentes', e.incidente_id]);
      return;
    }
    this.creando.set(e.id);
    this.aviso.set(null);
    try {
      const incidente = await this.api.incidenteDesdeEvento(e.id);
      this.feed.update((lista) =>
        lista.map((x) => (x.id === e.id ? { ...x, incidente_id: incidente.id } : x)),
      );
      await this.router.navigate(['/incidentes', incidente.id]);
    } catch (err) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(err) });
    } finally {
      this.creando.set(null);
    }
  }
}
