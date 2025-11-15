MRF.correctBoundaryVelocity(U);

if (laser.powderSim())
{
    DC =
        DarcyConstantlarge*Foam::pow((1.0-epsilon1mask),2)
       /(Foam::pow(epsilon1mask, 3) + DarcyConstantsmall);
}
else
{
    DC =
        DarcyConstantlarge*Foam::pow((1.0 - epsilon1), 2)
       /(Foam::pow(epsilon1, 3) + DarcyConstantsmall);
}

gradAlpha = fvc::grad(alpha1);
nHatM = gradAlpha/(mag(gradAlpha) + deltaN);
Marangoni =
    epsilon1*Marangoni_Constant*(gradT - nHatM*(nHatM & gradT))*mag(gradAlpha);

const scalar Tliquidus1Value = Tliquidus1.value();
const scalarField& TI = T;
vectorField& MarangoniI = Marangoni;

forAll(MarangoniI, celli)
{
    if(TI[celli] < Tliquidus1Value)
    {
        MarangoniI[celli] = vector::zero;
    }
}

Marangoni.correctBoundaryConditions();

if (damperSwitch)
{
    // To account for high density difference
    damper = 2.0*rho/(rho1 + rho2);
}

const scalar recoil_damper = 1;

// Calculate recoil pressure using original equation without temperature clamping
pVap = recoil_damper * 0.5 * (1 + beta_r) * p0* Foam::exp(LatentHeatVap*Mm*((T - Tvap)/(R*T*Tvap))); 

// Apply simple cutoff for recoil pressure
const scalar TvapValue = Tvap.value();
scalarField& pVapI = pVap;

forAll(pVapI, celli)
{
    if(TI[celli] < TvapValue)
    {
        // Below Tvap: no recoil pressure
        pVapI[celli] = 0.0;
    }
    // Above Tvap: full recoil pressure (already calculated)
}

pVap.correctBoundaryConditions();

fvVectorMatrix UEqn
(
    fvm::ddt(rho, U)
  + fvm::div(rhoPhi, U)
  + MRF.DDt(rho, U)
  + turbulence.divDevTau(rho, U)
  + fvm::Sp(DC, U)
  - Marangoni*damper
 ==
    phaseChange.SU(rho, rhoPhi, U)
  + fvModels.source(rho, U)
);

UEqn.relax();

fvConstraints.constrain(UEqn);

if (pimple.momentumPredictor())
{
    solve
    (
        UEqn
     ==
        fvc::reconstruct
        (
            (
                mixture.surfaceTensionForce()*fvc::interpolate(damper)
              + fvc::interpolate(pVap)
               *fvc::snGrad(alpha1)
               *fvc::interpolate(damper)
              - ghf*fvc::snGrad(rho*rhok)
              - fvc::snGrad(p_rgh)
            )*mesh.magSf()
        )
    );
    
    fvConstraints.constrain(U);
}














//Transition code
// MRF.correctBoundaryVelocity(U);

// if (laser.powderSim())
// {
//     DC =
//         DarcyConstantlarge*Foam::pow((1.0-epsilon1mask),2)
//       /(Foam::pow(epsilon1mask, 3) + DarcyConstantsmall);
// }
// else
// {
//     DC =
//         DarcyConstantlarge*Foam::pow((1.0 - epsilon1), 2)
//       /(Foam::pow(epsilon1, 3) + DarcyConstantsmall);
// }

// gradAlpha = fvc::grad(alpha1);
// nHatM = gradAlpha/(mag(gradAlpha) + deltaN);

// Marangoni =
//     epsilon1*Marangoni_Constant*(gradT - nHatM*(nHatM & gradT))*mag(gradAlpha);

// const scalar Tliquidus1Value = Tliquidus1.value();
// const scalarField& TI = T;
// vectorField& MarangoniI = Marangoni;

// forAll(MarangoniI, celli)
// {
//     if(TI[celli] < Tliquidus1Value)
//     {
//         MarangoniI[celli] = vector::zero;
//     }
// }

// Marangoni.correctBoundaryConditions();

// if (damperSwitch)
// {
//     // To account for high density difference
//     damper = 2.0*rho/(rho1 + rho2);
// }

// const scalar recoil_damper = 1;

// // Calculate recoil pressure using original equation without temperature clamping
// pVap = recoil_damper * 0.5 * (1 + beta_r) * p_amb * Foam::exp(LatentHeatVap*Mm*((T - Tvap)/(R*T*Tvap))); 

// // Define transition zone parameters
// const scalar TvapValue = Tvap.value();
// const scalar transitionWidth = 100.0;  // 100K transition zone above Tvap
// const scalar TupperBound = TvapValue + transitionWidth;  // Tvap + 100K

// // Apply transition for recoil pressure
// scalarField& pVapI = pVap;
// forAll(pVapI, celli)
// {
//     if(TI[celli] < TvapValue)
//     {
//         // Below Tvap: no recoil pressure
//         pVapI[celli] = 0.0;
//     }
//     else if(TI[celli] > TupperBound)
//     {
//         // Above Tvap + 100K: full recoil pressure (already calculated)
//         // pVapI[celli] remains as calculated above
//     }
//     else
//     {
//         // Within transition zone [Tvap, Tvap + 100K]: apply smooth scaling factor
//         scalar deltaT = TI[celli] - TvapValue;
//         scalar normalizedDelta = deltaT / transitionWidth;  // 0 to 1 over transition
        
//         // Use smooth sigmoid-like function for transition
//         // This creates a smooth S-curve from 0 to 1
//         // scalar smoothFactor = 0.5 * (1.0 + Foam::tanh(4.0 * (normalizedDelta - 0.5)));
        
//         // Alternative: simpler polynomial transition (uncomment if preferred)
//         scalar smoothFactor = normalizedDelta * normalizedDelta * (3.0 - 2.0 * normalizedDelta);
        
//         pVapI[celli] *= smoothFactor;
//     }
// }

// pVap.correctBoundaryConditions();

// fvVectorMatrix UEqn
// (
//     fvm::ddt(rho, U)
//   + fvm::div(rhoPhi, U)
//   + MRF.DDt(rho, U)
//   + turbulence.divDevTau(rho, U)
//   + fvm::Sp(DC, U)
//   - Marangoni*damper
//  ==
//     phaseChange.SU(rho, rhoPhi, U)
//   + fvModels.source(rho, U)
// );

// UEqn.relax();
// fvConstraints.constrain(UEqn);

// if (pimple.momentumPredictor())
// {
//     solve
//     (
//         UEqn
//      ==
//         fvc::reconstruct
//         (
//             (
//                 mixture.surfaceTensionForce()*fvc::interpolate(damper)
//               + fvc::interpolate(pVap)
//               *fvc::snGrad(alpha1)
//               *fvc::interpolate(damper)
//               - ghf*fvc::snGrad(rho*rhok)
//               - fvc::snGrad(p_rgh)
//             )*mesh.magSf()
//         )
//     );
    
//     fvConstraints.constrain(U);
// }