from pathlib import Path
OUT=Path(__file__).parent
code=(OUT/'check_lattice.py').read_text()
code=code.replace("ROOT/'parts'","ROOT/'print-parts'")
code=code.replace(' actual[name]=md.Manifold',' t.apply_scale([1/1.3,1,1])\n actual[name]=md.Manifold')
code=code.replace("ROOT/'lattice-validation.json'","ROOT/'final-lattice-validation.json'")
exec(compile(code,str(OUT/'check_lattice.py'),'exec'))
