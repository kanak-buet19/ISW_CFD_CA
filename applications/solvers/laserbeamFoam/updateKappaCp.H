{

    const scalarField& alpha1I = alpha1;

    const scalarField& TI = T;

    scalarField& kappaI = kappa;

    scalarField& cpI = cp;



    forAll(kappaI, celli)

    {

        // Metal phase uses interpolation table

        kappaI[celli] =

            max(min(alpha1I[celli], 1.0), 0.0) * kappaTab_m(TI[celli])

          + (1.0 - max(min(alpha1I[celli], 1.0), 0.0)) * polykappa_g.value(TI[celli]);



        cpI[celli] =

            max(min(alpha1I[celli], 1.0), 0.0) * cpTab_m(TI[celli])

          + (1.0 - max(min(alpha1I[celli], 1.0), 0.0)) * polycp_g.value(TI[celli]);

    }



    kappa.correctBoundaryConditions();

    cp.correctBoundaryConditions();

}


