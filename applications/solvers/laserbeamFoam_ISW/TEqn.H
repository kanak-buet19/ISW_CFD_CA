{
    int iter = 0;
    scalarField residual(epsilon1.primitiveField().size(), 1.0);
    scalar maxResidual = 1.0;
    scalar meanResidual = 1.0;
    scalar Tresidual = 1.0;

    TRHS *= 0.0;

    rhoCp = rho*cp;
    rhophicp = fvc::interpolate(cp)*rhoPhi;

    // const volTensorField gradU(fvc::grad(U));
    // volTensorField tau
    // (
    //     ((mixture.mu()*gradU) + (mixture.mu()*gradU.T()))
    //   - ((2.0/3.0)*mixture.mu()*(fvc::div(phi))*I)
    // );

    do
    {
        epsilon1.storePrevIter();
        T.storePrevIter();
        TRHS =
            LatentHeat*((fvc::ddt(rho, epsilon1) + fvc::div(rhoPhi, epsilon1)));

        Qv =
            0.82*LatentHeatVap*Mm*p0
           *Foam::exp(LatentHeatVap*Mm*((T - Tvap_atm)/(R*T*Tvap_atm)))
           /Foam::pow(2*M_PI*Mm*R*T,0.5);


        // Calculate radiation heat transfer (Stefan-Boltzmann law)
        Qrad = emissivity * stefanBoltzmann * (pow4(T) - pow4(T_ambient));

        // Calculate convection heat transfer (Newton's law of cooling)  
        Qconv = h_convection * (T - T_ambient);

        // // Apply temperature threshold for evaporative cooling - only active when T > Tvap
        // const scalar TvapValue = Tvap.value();
        // const scalarField& TI = T;
        // scalarField& QvI = Qv;

        // forAll(QvI, celli)
        // {
        //     if(TI[celli] <= TvapValue)
        //     {
        //         QvI[celli] = 0.0;  // No evaporation below vaporization temperature
        //     }
        // }

        Qv.correctBoundaryConditions();

        if (damperSwitch)
        {
            scalarField& thermalDamperI = thermalDamper;
            const scalarField& rhoCpI = rhoCp;
            forAll(thermalDamperI, celli)
            {
		 thermalDamperI[celli] =
		    2.0*rhoCpI[celli]
		   /(
		    (rho1.value() * cpTab_m(TI[celli]))
		  + (rho2.value() * polycp_g.value(TI[celli]))
		   );

            }

            thermalDamper.correctBoundaryConditions();
        }

        fvScalarMatrix TEqn
        (
            fvm::ddt(rhoCp,T)
          + fvm::div(rhophicp, T)
          - fvm::Sp(fvc::ddt(rhoCp) + fvc::div(rhophicp), T)
          - fvm::laplacian(kappa, T)
          //- (tau && gradU) // Viscous dissipation
         ==
            fvModels.source(rhoCp,T)
          + laser.deposition()
        //   + laser.deposition() *mag(gradAlpha)*thermalDamper
          - Qv*mag(gradAlpha)*thermalDamper 
          - Qrad*mag(gradAlpha)*thermalDamper    // Radiation heat loss
          - Qconv*mag(gradAlpha)*thermalDamper   // Convection heat loss
          - TRHS
        );

        TEqn.relax();

        fvConstraints.constrain(TEqn);

        TEqn.solve();

        T.relax();

        Tcorr = (TLiquidus - TSolidus)*epsilon1 + TSolidus;

        epsilon1 =
            max
            (
                min
                (
                    epsilon1 + (epsilonRel*cp/LatentHeat)*(T - Tcorr),
                    scalar(1)
                ),
                scalar(0)
            );

        residual =
            mag
            (
                epsilon1.primitiveField()
              - epsilon1.prevIter().primitiveField()
            );

        maxResidual = gMax(residual);

        meanResidual = gSum(residual*mesh.V())/gSum(mesh.V().field());

        //ddte1 = fvc::ddt(epsilon1);

        Info<< "Correcting epsilon1, mean residual = " << meanResidual
            << ", max residual = " << maxResidual
            << endl;
    }
    while
    (
        (
            ++iter < minTCorr
         // || (meanResidual > epsilonTol.value())
         || (maxResidual > epsilonTol.value())
        )
     && iter <= maxTCorr
    );

    gradT = fvc::grad(T);
}