export class ScrcpyDecoder {
  private decoder: VideoDecoder | null = null
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  private sps: Uint8Array | null = null
  private pps: Uint8Array | null = null
  private codecString = 'avc1.42001E'
  private configured = false
  private pendingFrames: Uint8Array[] = []
  private lastFrameTime = 0

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法获取 Canvas 2D 上下文')
    this.ctx = ctx
  }

  async init() {
    if (!('VideoDecoder' in window)) {
      throw new Error('当前浏览器不支持 WebCodecs，请使用 Chrome/Edge 最新版')
    }
    this.decoder = new VideoDecoder({
      output: (frame) => {
        this.canvas.width = frame.displayWidth
        this.canvas.height = frame.displayHeight
        this.ctx.drawImage(frame, 0, 0)
        frame.close()
      },
      error: (e) => {
        console.error('VideoDecoder error:', e)
      },
    })
  }

  feed(data: Uint8Array) {
    if (!this.decoder) return

    const naluType = this.getNaluType(data)

    if (naluType === 7) {
      this.sps = data
      this.codecString = this.parseCodecString(data)
      this.configured = false
    } else if (naluType === 8) {
      this.pps = data
      this.configured = false
    }

    if (!this.configured && this.sps && this.pps) {
      const description = this.buildAvccDescription(this.sps, this.pps)
      try {
        this.decoder.configure({
          codec: this.codecString,
          hardwareAcceleration: 'prefer-hardware',
          description,
        })
        this.configured = true
        for (const frame of this.pendingFrames) {
          this._decodeFrame(frame)
        }
        this.pendingFrames = []
      } catch (e) {
        console.error('Decoder configure error:', e)
      }
    }

    if (!this.configured) {
      this.pendingFrames.push(data)
      return
    }

    this._decodeFrame(data)
  }

  destroy() {
    this.decoder?.close()
    this.decoder = null
    this.sps = null
    this.pps = null
    this.configured = false
    this.pendingFrames = []
  }

  private getNaluType(data: Uint8Array): number {
    if (data.length < 5) return -1
    if (data[0] === 0 && data[1] === 0 && data[2] === 0 && data[3] === 1) {
      return data[4] & 0x1f
    }
    if (data[0] === 0 && data[1] === 0 && data[2] === 1) {
      return data[3] & 0x1f
    }
    return -1
  }

  private parseCodecString(sps: Uint8Array): string {
    let offset = 0
    if (sps[0] === 0 && sps[1] === 0 && sps[2] === 0 && sps[3] === 1) {
      offset = 5
    } else if (sps[0] === 0 && sps[1] === 0 && sps[2] === 1) {
      offset = 4
    }
    const profileIdc = sps[offset]
    const constraintFlags = sps[offset + 1]
    const levelIdc = sps[offset + 2]
    const pp = profileIdc.toString(16).padStart(2, '0')
    const cc = constraintFlags.toString(16).padStart(2, '0')
    const ll = levelIdc.toString(16).padStart(2, '0')
    return `avc1.${pp}${cc}${ll}`
  }

  private buildAvccDescription(sps: Uint8Array, pps: Uint8Array): Uint8Array {
    let spsOffset = 0
    if (sps[0] === 0 && sps[1] === 0 && sps[2] === 0 && sps[3] === 1) {
      spsOffset = 5
    } else if (sps[0] === 0 && sps[1] === 0 && sps[2] === 1) {
      spsOffset = 4
    }
    let ppsOffset = 0
    if (pps[0] === 0 && pps[1] === 0 && pps[2] === 0 && pps[3] === 1) {
      ppsOffset = 5
    } else if (pps[0] === 0 && pps[1] === 0 && pps[2] === 1) {
      ppsOffset = 4
    }

    const spsPayload = sps.slice(spsOffset)
    const ppsPayload = pps.slice(ppsOffset)

    const desc = new Uint8Array(11 + spsPayload.length + ppsPayload.length)
    let i = 0
    desc[i++] = 1
    desc[i++] = spsPayload[0]
    desc[i++] = spsPayload[1]
    desc[i++] = spsPayload[2]
    desc[i++] = 0xff
    desc[i++] = 0xe1
    desc[i++] = (spsPayload.length >> 8) & 0xff
    desc[i++] = spsPayload.length & 0xff
    desc.set(spsPayload, i)
    i += spsPayload.length
    desc[i++] = 1
    desc[i++] = (ppsPayload.length >> 8) & 0xff
    desc[i++] = ppsPayload.length & 0xff
    desc.set(ppsPayload, i)

    return desc
  }

  private annexbToAvcc(data: Uint8Array): Uint8Array {
    const parts: Uint8Array[] = []
    let idx = 0
    while (idx < data.length - 3) {
      let startLen = 0
      if (data[idx] === 0 && data[idx + 1] === 0 && data[idx + 2] === 0 && data[idx + 3] === 1) {
        startLen = 4
      } else if (data[idx] === 0 && data[idx + 1] === 0 && data[idx + 2] === 1) {
        startLen = 3
      }
      if (startLen > 0) {
        let j = idx + startLen
        while (j < data.length - 3) {
          if (
            (data[j] === 0 && data[j + 1] === 0 && data[j + 2] === 0 && data[j + 3] === 1) ||
            (data[j] === 0 && data[j + 1] === 0 && data[j + 2] === 1)
          ) {
            break
          }
          j++
        }
        const payload = data.slice(idx + startLen, j)
        const lenBuf = new ArrayBuffer(4)
        new DataView(lenBuf).setUint32(0, payload.length, false)
        parts.push(new Uint8Array(lenBuf))
        parts.push(payload)
        idx = j
      } else {
        idx++
      }
    }

    let totalLen = 0
    for (const p of parts) totalLen += p.length
    const output = new Uint8Array(totalLen)
    let offset = 0
    for (const p of parts) {
      output.set(p, offset)
      offset += p.length
    }
    return output
  }

  private _decodeFrame(data: Uint8Array) {
    if (!this.decoder) return
    const naluType = this.getNaluType(data)
    if (naluType === 7 || naluType === 8) return

    const avccData = this.annexbToAvcc(data)
    if (avccData.length === 0) return

    const isKeyFrame = naluType === 5
    const chunk = new EncodedVideoChunk({
      type: isKeyFrame ? 'key' : 'delta',
      timestamp: performance.now() * 1000,
      data: avccData,
    })

    try {
      this.decoder.decode(chunk)
    } catch (e) {
      console.error('Decode error:', e)
    }
  }
}
