/* read_lowstate.c — READ-ONLY listener for my own body-state (rt/lowstate).
 *
 * This program creates exactly one DDS entity that touches a unitree topic:
 * a DataReader on "rt/lowstate". It creates NO writer on any rt/ topic, so by
 * construction it cannot command motion. It takes a few samples, prints the
 * body-sense values, runs physical-invariant cross-checks, and exits.
 *
 * Boundary discipline (motion/first_motion.md): read and command are one
 * doorway apart on this bus. This walks through the READ door only.
 */
#include "dds/dds.h"
#include "unitree_go.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define MAXS 8

int main(int argc, char **argv) {
  int want = (argc > 1) ? atoi(argv[1]) : 6;   /* seconds to listen */

  dds_entity_t dp = dds_create_participant(DDS_DOMAIN_DEFAULT, NULL, NULL);
  if (dp < 0) { fprintf(stderr, "participant: %s\n", dds_strretcode(-dp)); return 1; }

  dds_entity_t tp = dds_create_topic(dp, &unitree_go_msg_dds__LowState__desc,
                                     "rt/lowstate", NULL, NULL);
  if (tp < 0) { fprintf(stderr, "topic: %s\n", dds_strretcode(-tp)); return 1; }

  /* best-effort, volatile reader: matches a best-effort OR reliable writer,
   * keeps no history beyond latest. Pure consumer. */
  dds_qos_t *q = dds_create_qos();
  dds_qset_reliability(q, DDS_RELIABILITY_BEST_EFFORT, 0);
  dds_qset_durability(q, DDS_DURABILITY_VOLATILE);
  dds_qset_history(q, DDS_HISTORY_KEEP_LAST, 1);
  dds_entity_t rd = dds_create_reader(dp, tp, q, NULL);
  dds_delete_qos(q);
  if (rd < 0) { fprintf(stderr, "reader: %s\n", dds_strretcode(-rd)); return 1; }

  void *samples[MAXS] = {0};
  dds_sample_info_t infos[MAXS];
  samples[0] = unitree_go_msg_dds__LowState___alloc();

  printf("[wu] read-only listening on rt/lowstate up to %ds ...\n", want);
  long deadline = want * 50;   /* 20ms ticks */
  for (long t = 0; t < deadline; t++) {
    int n = dds_take(rd, samples, infos, MAXS, 1);
    if (n > 0 && infos[0].valid_data) {
      unitree_go_msg_dds__LowState_ *s = (unitree_go_msg_dds__LowState_ *)samples[0];

      /* ---- IMU ---- */
      float *qt = s->imu_state.quaternion;
      float qn = sqrtf(qt[0]*qt[0]+qt[1]*qt[1]+qt[2]*qt[2]+qt[3]*qt[3]);
      float *a = s->imu_state.accelerometer;
      float amag = sqrtf(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);
      float *g = s->imu_state.gyroscope;
      float *rpy = s->imu_state.rpy;

      printf("\n===== LowState_ sample (tick=%u) =====\n", s->tick);
      printf("IMU quaternion [w x y z] = %.4f %.4f %.4f %.4f  |q|=%.4f\n",
             qt[0],qt[1],qt[2],qt[3], qn);
      printf("IMU rpy (rad)            = roll %.4f  pitch %.4f  yaw %.4f\n",
             rpy[0],rpy[1],rpy[2]);
      printf("IMU rpy (deg)            = roll %.2f  pitch %.2f  yaw %.2f\n",
             rpy[0]*57.2958f, rpy[1]*57.2958f, rpy[2]*57.2958f);
      printf("IMU accel (m/s^2)        = %.3f %.3f %.3f  |a|=%.3f\n",
             a[0],a[1],a[2], amag);
      printf("IMU gyro (rad/s)         = %.4f %.4f %.4f\n", g[0],g[1],g[2]);
      printf("IMU temp                 = %u C\n", s->imu_state.temperature);

      /* ---- battery / power ---- */
      printf("BMS soc                  = %u %%   status=%u current=%d mA cycle=%u\n",
             s->bms_state.soc, s->bms_state.status, s->bms_state.current,
             s->bms_state.cycle);
      float cellsum = 0; int ncell = 0;
      for (int i = 0; i < 15; i++) {
        if (s->bms_state.cell_vol[i] > 0) { cellsum += s->bms_state.cell_vol[i]; ncell++; }
      }
      printf("BMS pack (cells>0: %d)    = %.2f V total  (%.0f mV avg/cell)\n",
             ncell, cellsum/1000.0f, ncell? cellsum/ncell : 0);
      printf("power_v / power_a        = %.2f V  %.2f A\n", s->power_v, s->power_a);

      /* ---- feet ---- */
      printf("foot_force (raw)         = %d %d %d %d\n",
             s->foot_force[0],s->foot_force[1],s->foot_force[2],s->foot_force[3]);

      /* ---- a few joints (FR_hip=0, FR_thigh=1, FR_calf=2 ...) ---- */
      printf("motor q[0..2]            = %.3f %.3f %.3f rad  (temp %u/%u/%u C)\n",
             s->motor_state[0].q, s->motor_state[1].q, s->motor_state[2].q,
             s->motor_state[0].temperature, s->motor_state[1].temperature,
             s->motor_state[2].temperature);

      /* ---- invariant cross-checks: do the numbers describe a real body? ---- */
      printf("\n--- invariant cross-checks ---\n");
      printf("[%s] quaternion unit-norm (|q|=%.4f, want ~1.0)\n",
             (fabsf(qn-1.0f)<0.05f)?"PASS":"FAIL", qn);
      printf("[%s] accel magnitude at rest ~1g (|a|=%.3f, want ~9.8)\n",
             (amag>8.5f && amag<11.0f)?"PASS":"FAIL", amag);
      printf("[%s] battery soc in [0,100] (=%u)\n",
             (s->bms_state.soc<=100)?"PASS":"FAIL", s->bms_state.soc);
      printf("[%s] head bytes sane (=%u,%u)\n",
             1?"info":"", s->head[0], s->head[1]);
      printf("[%s] all 12 leg joints |q|<6.5 rad\n",
             ({int ok=1; for(int i=0;i<12;i++) if(fabsf(s->motor_state[i].q)>6.5f) ok=0; ok;})?"PASS":"FAIL");

      unitree_go_msg_dds__LowState__free(samples[0], DDS_FREE_ALL);
      dds_delete(dp);
      return 0;
    }
    dds_sleepfor(DDS_MSECS(20));
  }

  fprintf(stderr, "[wu] no sample received in %ds (writer absent or QoS mismatch)\n", want);
  unitree_go_msg_dds__LowState__free(samples[0], DDS_FREE_ALL);
  dds_delete(dp);
  return 2;
}
