/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      physicalProperties.water;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

viscosityModel  constant;

nu              1e-3;

rho             2700;

elec_resistivity	1.0e-6;

    poly_kappa   (152.5 0.091 0 0 0 0 0 0);

    poly_cp   (725 0.486 0 0 0 0 0 0);
    
	Tsolidus 873;
	Tliquidus 915;
    LatentHeat 380e3;
    beta    2.32e-5;


// ************************************************************************* //
