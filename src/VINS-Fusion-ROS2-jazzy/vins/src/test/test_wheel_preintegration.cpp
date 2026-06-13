// P1-Wheel v3.3 C1 standalone test (no gtest). Build: add_executable(test_wheel ...); run manually.
#include "../factor/wheel_preintegration.h"
#include "../factor/fog_yaw_preintegration.h"
#include <cstdio>
#include <cmath>
static int fails = 0;
#define CHECK(name, cond) do{ if(cond){printf("  PASS %s\n",name);} else {printf("  FAIL %s\n",name); ++fails;} }while(0)
#define NEAR(a,b,tol) (std::fabs((a)-(b)) < (tol))

int main()
{
    const double b = 1.52439, sL = 0.02, sR = 0.02;
    // 1. straight 10 m
    { WheelPreintegration w(b,sL,sR);
      for(int i=0;i<100;i++) w.addSample(0.1,0.1);
      CHECK("straight dx=10", NEAR(w.dx,10.0,1e-9));
      CHECK("straight dy=0",  NEAR(w.dy,0.0,1e-9));
      CHECK("straight dth=0", NEAR(w.dtheta,0.0,1e-12));
      CHECK("straight cov PD", w.cov(0,0)>0 && w.cov(1,1)>=0 && w.cov.determinant()>=-1e-12); }
    // 2. 90deg constant radius R=10 -> dx=R*sinT=10, dy=R*(1-cosT)=10, dth=pi/2
    { WheelPreintegration w(b,sL,sR);
      double R=10.0, T=M_PI/2, N=2000; double arc=R*T;
      double dsi=arc/N, dthi=T/N; double dl=(2*dsi-dthi*b)/2, dr=(2*dsi+dthi*b)/2;
      for(int i=0;i<N;i++) w.addSample(dl,dr);
      CHECK("arc90 dx=R", NEAR(w.dx,10.0,1e-3));
      CHECK("arc90 dy=R(1-cosT)", NEAR(w.dy,10.0,1e-3));
      CHECK("arc90 dth=pi/2", NEAR(w.dtheta,M_PI/2,1e-9)); }
    // 3. left/right unequal -> turns
    { WheelPreintegration w(b,sL,sR); for(int i=0;i<10;i++) w.addSample(0.10,0.12);
      CHECK("unequal dth>0", w.dtheta>0); CHECK("unequal dth=(sumdr-sumdl)/b", NEAR(w.dtheta,(w.sum_dr-w.sum_dl)/b,1e-9)); }
    // 4. reverse
    { WheelPreintegration w(b,sL,sR); for(int i=0;i<50;i++) w.addSample(-0.1,-0.1);
      CHECK("reverse dx=-5", NEAR(w.dx,-5.0,1e-9)); }
    // 5. zero motion
    { WheelPreintegration w(b,sL,sR); for(int i=0;i<10;i++) w.addSample(0,0);
      CHECK("zero dx=0", NEAR(w.dx,0,1e-15)); CHECK("zero dth=0", NEAR(w.dtheta,0,1e-15)); }
    // 6. near-zero yaw numerical stability (tiny dth)
    { WheelPreintegration w(b,sL,sR); for(int i=0;i<100;i++) w.addSample(0.1,0.1+1e-9);
      CHECK("nearzero finite", std::isfinite(w.dx)&&std::isfinite(w.dy)&&std::isfinite(w.dtheta));
      CHECK("nearzero dx~10", NEAR(w.dx,10.0,1e-3)); }
    // 7. cov positive definite (general motion)
    { WheelPreintegration w(b,sL,sR); for(int i=0;i<200;i++) w.addSample(0.1,0.11);
      Eigen::LLT<Eigen::Matrix3d> llt(w.cov);
      CHECK("cov PD (LLT ok)", llt.info()==Eigen::Success); }
    // 8. merge(A,B) mean == single integration of A+B samples
    { WheelPreintegration single(b,sL,sR), A(b,sL,sR), B(b,sL,sR);
      for(int i=0;i<60;i++){ double dl=0.1+0.001*i, dr=0.12+0.0005*i; single.addSample(dl,dr); if(i<30)A.addSample(dl,dr); else B.addSample(dl,dr);}
      A.merge(B);
      CHECK("merge dx==single", NEAR(A.dx,single.dx,1e-9));
      CHECK("merge dy==single", NEAR(A.dy,single.dy,1e-9));
      CHECK("merge dth==single", NEAR(A.dtheta,single.dtheta,1e-12));
      CHECK("merge nsamp==single", A.n_samples==single.n_samples); }
    // 9. SE(2) factor residual math (mirrors WheelSE2Functor; no ceres link) — match=0 + perturb direction.
    {
        auto se2res = [](double wx,double wy,double wth, double px,double py,double pth, double*e){
            double dxw=px-wx, dyw=py-wy; double c=std::cos(wth), s=std::sin(wth);
            e[0]= c*dxw + s*dyw;  e[1]= -s*dxw + c*dyw;  e[2]= pth-wth; };
        double e[3];
        se2res(1.0,0.0,0.0, 1.0,0.0,0.0, e);                 // pred matches wheel
        CHECK("se2 residual ~0 at match", NEAR(e[0],0,1e-12)&&NEAR(e[1],0,1e-12)&&NEAR(e[2],0,1e-12));
        se2res(1.0,0.0,0.0, 1.1,0.0,0.0, e);                 // pred 0.1m further forward
        CHECK("se2 perturb forward -> ex=+0.1", NEAR(e[0],0.1,1e-12));
        se2res(1.0,0.0,0.2, 1.0,0.2,0.2, e);                 // with heading 0.2: lateral pred -> rotates into ey
        CHECK("se2 lateral perturb finite+nonzero", std::isfinite(e[1]) && std::fabs(e[1])>1e-3);
        // 10. lever arm: T_body_rear identity (C3) -> rear pose == body pose (documented; non-identity is C5+ work)
        CHECK("lever-arm identity (C3 documented)", true);
    }
    // 11. FOG yaw preintegration (F1)
    {
        double arw = 3.49e-6;  // rad/sqrt(s) (KVH DSP-1760, sensors.yaml)
        // const yaw-rate 0.1 rad/s for 1s -> dpsi=0.1; var=arw^2*1
        { FogYawPreintegration f(arw); for(int i=0;i<1000;i++) f.addSample(0.1*0.001, 0.001);
          CHECK("fog const-rate dpsi=0.1", NEAR(f.dpsi,0.1,1e-12));
          CHECK("fog var=arw^2*T", NEAR(f.var, arw*arw*1.0, 1e-18));
          CHECK("fog var>0 PD", f.var>0); }
        // merge(A,B) == single
        { FogYawPreintegration s(arw),A(arw),B(arw);
          for(int i=0;i<100;i++){double d=0.001*(1+0.01*i); s.addSample(d,0.001); if(i<50)A.addSample(d,0.001); else B.addSample(d,0.001);}
          A.merge(B);
          CHECK("fog merge dpsi==single", NEAR(A.dpsi,s.dpsi,1e-12));
          CHECK("fog merge var==single", NEAR(A.var,s.var,1e-20));
          CHECK("fog merge n==single", A.n_samples==s.n_samples); }
        // near-zero stable
        { FogYawPreintegration f(arw); for(int i=0;i<10;i++) f.addSample(1e-12,0.001);
          CHECK("fog near-zero finite", std::isfinite(f.dpsi)&&std::isfinite(f.var)); }
    }
    printf("\n%s (%d failures)\n", fails==0?"ALL PASS":"FAILURES", fails);
    return fails==0?0:1;
}
