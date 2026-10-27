// Decompile every function of a raw image (entries file: "<name> <hex address>") and report failures and
// "Low-level Error" / "Overlapping input varnodes" messages.
// Script args: <entries-file> <summary-file>
//@category Testing
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class DecompAll extends GhidraScript {
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[1]);
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		int n = 0, failed = 0, lowlevel = 0;
		for (String l : Files.readAllLines(Path.of(args[0]))) {
			String[] f = l.trim().split("\\s+");
			if (f.length < 2) {
				continue;
			}
			Address a = toAddr(Long.parseUnsignedLong(f[1], 16));
			disassemble(a);
			Function fn = createFunction(a, f[0]);
			if (fn == null) {
				continue;
			}
			n++;
			DecompileResults r = di.decompileFunction(fn, 30, monitor);
			String c = r.getDecompiledFunction() == null ? "" : r.getDecompiledFunction().getC();
			if (!r.decompileCompleted()) {
				failed++;
				out.println("FAILED " + f[0] + " " + f[1] + ": " + r.getErrorMessage());
				di.closeProgram();
				di.openProgram(currentProgram);
			}
			else if (c.contains("Low-level Error") || c.contains("Overlapping") || c.contains("Unable to")) {
				lowlevel++;
				out.println("LOWLEVEL " + f[0] + " " + f[1]);
			}
		}
		out.printf("decompiled %d functions, %d failed, %d with low-level errors%n", n, failed, lowlevel);
		out.close();
	}
}
