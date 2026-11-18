/* Regression checks against the actual shared FFmpeg library. */
#include <assert.h>
#include <limits.h>
#include <stdarg.h>
#include <string.h>
#include <sys/resource.h>

#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavformat/avformat.h>
#include <libavutil/encryption_info.h>
#include <libavutil/hdr_dynamic_metadata.h>
#include <libavutil/mem.h>
#include <libavutil/rational.h>

static AVBSFContext *filter(const char *name, enum AVCodecID codec)
{
    AVBSFContext *ctx = NULL;
    const AVBitStreamFilter *bsf = av_bsf_get_by_name(name);
    assert(bsf && av_bsf_alloc(bsf, &ctx) == 0);
    ctx->par_in->codec_id = codec;
    assert(av_bsf_init(ctx) == 0);
    return ctx;
}

static void check_aac(void)
{
    AVBSFContext *ctx = filter("aac_adtstoasc", AV_CODEC_ID_AAC);
    AVPacket *pkt = av_packet_alloc();
    /* A valid ADTS header with channel configuration zero enters the PCE path.
     * Keep the large allocation sparse; only the header and padding are read. */
    const uint8_t header[] = {0xff, 0xf1, 0x50, 0x00, 0x01, 0x1f, 0xfc};
    assert(pkt && av_new_packet(pkt, INT_MAX / 8 + 64) == 0);
    memcpy(pkt->data, header, sizeof(header));
    assert(av_bsf_send_packet(ctx, pkt) == 0);
    assert(av_bsf_receive_packet(ctx, pkt) == AVERROR_INVALIDDATA);
    av_packet_free(&pkt);
    av_bsf_free(&ctx);
}

static int send_obus(AVBSFContext *ctx, int count, int delimiter)
{
    AVPacket *pkt = av_packet_alloc();
    assert(pkt && av_new_packet(pkt, count * 2) == 0);
    for (int i = 0; i < count; i++) {
        pkt->data[i * 2] = i == 0 && delimiter ? 0x12 : 0x7a;
        pkt->data[i * 2 + 1] = 0;
    }
    assert(av_bsf_send_packet(ctx, pkt) == 0);
    int ret = av_bsf_receive_packet(ctx, pkt);
    av_packet_free(&pkt);
    return ret;
}

static void check_av1(int accumulated)
{
    AVBSFContext *ctx = filter("av1_frame_merge", AV_CODEC_ID_AV1);
    if (accumulated) {
        assert(send_obus(ctx, 32769, 1) == AVERROR(EAGAIN));
        assert(send_obus(ctx, 32768, 0) == AVERROR_INVALIDDATA);
    } else {
        assert(send_obus(ctx, 65537, 1) == AVERROR_INVALIDDATA);
    }
    /* A rejected temporal unit must not poison later packets. */
    assert(send_obus(ctx, 2, 1) == AVERROR(EAGAIN));
    av_bsf_free(&ctx);
}

static int corrupt_extradata_errors;

static void count_vorbis_errors(void *ptr, int level, const char *fmt, va_list args)
{
    (void)ptr;
    (void)level;
    (void)args;
    if (strcmp(fmt, "Extradata corrupt.\n") == 0)
        corrupt_extradata_errors++;
}

static void check_vorbis(void)
{
    AVCodecParserContext *parser = av_parser_init(AV_CODEC_ID_VORBIS);
    AVCodecContext *ctx = avcodec_alloc_context3(NULL);
    uint8_t input[1 + AV_INPUT_BUFFER_PADDING_SIZE] = {0};
    uint8_t *output;
    int output_size;
    assert(parser && ctx);
    ctx->extradata_size = 3;
    ctx->extradata = av_mallocz(ctx->extradata_size + AV_INPUT_BUFFER_PADDING_SIZE);
    assert(ctx->extradata);
    av_log_set_callback(count_vorbis_errors);
    for (int i = 0; i < 1000; i++) {
        assert(av_parser_parse2(parser, ctx, &output, &output_size, input, 1,
                                AV_NOPTS_VALUE, AV_NOPTS_VALUE, 0) == 1);
        assert(output_size == 1);
    }
    assert(corrupt_extradata_errors == 1);
    av_log_set_callback(av_log_default_callback);
    av_parser_close(parser);
    avcodec_free_context(&ctx);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    if (strcmp(argv[1], "flac-disabled") == 0) {
        assert(avcodec_find_decoder(AV_CODEC_ID_FLAC) == NULL);
        assert(av_parser_init(AV_CODEC_ID_FLAC) == NULL);
        assert(av_find_input_format("flac") == NULL);
    } else if (strcmp(argv[1], "aac") == 0) {
        check_aac();
    } else if (strcmp(argv[1], "av1-packet") == 0) {
        check_av1(0);
    } else if (strcmp(argv[1], "av1-buffer") == 0) {
        check_av1(1);
    } else if (strcmp(argv[1], "vorbis") == 0) {
        check_vorbis();
    } else if (strcmp(argv[1], "encryption") == 0) {
        AVEncryptionInitInfo *head = NULL;
        struct rlimit stack = {128 * 1024, 128 * 1024};
        assert(setrlimit(RLIMIT_STACK, &stack) == 0);
        for (int i = 0; i < 100000; i++) {
            AVEncryptionInitInfo *node = av_encryption_init_info_alloc(0, 0, 0, 0);
            assert(node);
            node->next = head;
            head = node;
        }
        av_encryption_init_info_free(head);
    } else {
        assert(strcmp(argv[1], "hdr") == 0);
        AVDynamicHDRPlus *hdr = av_dynamic_hdr_plus_alloc(NULL);
        AVDynamicHDRPlus *parsed = av_dynamic_hdr_plus_alloc(NULL);
        assert(hdr && parsed);
        hdr->num_windows = 1;
        hdr->targeted_system_display_maximum_luminance.den = 1;
        for (int i = 0; i < 3; i++)
            hdr->params[0].maxscl[i].den = 1;
        hdr->params[0].average_maxrgb.den = 1;
        hdr->params[0].fraction_bright_pixels.den = 1;
        hdr->params[0].color_saturation_mapping_flag = 1;
        hdr->params[0].color_saturation_weight = (AVRational){1, 1};
        size_t size;
        assert(av_dynamic_hdr_plus_to_t35(hdr, NULL, &size) == 0);
        uint8_t *data = av_malloc(size);
        assert(data);
        memset(data, 0xa5, size);
        assert(av_dynamic_hdr_plus_to_t35(hdr, &data, &size) == 0);
        assert(av_dynamic_hdr_plus_from_t35(parsed, data, size) == 0);
        assert(parsed->params[0].tone_mapping_flag == 0);
        assert(parsed->params[0].color_saturation_mapping_flag == 1);
        assert(av_cmp_q(parsed->params[0].color_saturation_weight, (AVRational){1, 1}) == 0);
        av_free(data);
        av_free(parsed);
        av_free(hdr);
    }
    return 0;
}
