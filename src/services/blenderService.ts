import { exec } from 'child_process';
import { promisify } from 'util';
import { config } from '../config';

const execAsync = promisify(exec);

export async function executeBlenderScript(
  scriptPath: string,
  outputPath: string
): Promise<{ stdout: string; stderr: string }> {
  const command = `"${config.blenderPath}" --background --python "${scriptPath}" -- "${outputPath}"`;

  try {
    const result = await execAsync(command);
    return result;
  } catch (error: any) {
    throw new Error(`Blender execution failed: ${error.message}`);
  }
}
